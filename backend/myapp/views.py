import json
import requests
from decimal import Decimal
from uuid import UUID

from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction, OperationalError, connection
from django.db.models import Count, Q, F
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST, require_GET

from myapp.forms import ItemForm
from myapp.models import Inventory, Item, Location, ValuationRun, ValuationSourceResult, ComparableListing, Category, AttachmentType, Attachment


from inventory_manager.pipeline.ebay_client import search_ebay
from inventory_manager.pipeline.poc_valuation import estimate

def _attachment_file_url(attachment):
    """Keep private storage paths out of API responses."""
    return reverse("attachment-file", kwargs={"attachment_id": attachment.public_id})


@ensure_csrf_cookie
def auth_csrf(request):
    return JsonResponse({"detail": "CSRF cookie set"})


@require_POST
def auth_login(request):
    try:
        credentials = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request body."}, status=400)

    if not isinstance(credentials, dict):
        return JsonResponse({"error": "Username and password are required."}, status=400)

    username = credentials.get("username", "")
    password = credentials.get("password", "")
    if (
        not isinstance(username, str)
        or not isinstance(password, str)
        or not username
        or not password
    ):
        return JsonResponse({"error": "Username and password are required."}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"error": "Invalid username or password."}, status=401)

    login(request, user)
    return JsonResponse({"authenticated": True, "username": user.get_username()})


@require_POST
def auth_register(request):
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request body."}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"error": "Invalid request body."}, status=400)

    fields = {}
    for name in ("first_name", "last_name", "email", "username", "password", "password_confirm"):
        value = payload.get(name, "")
        if not isinstance(value, str):
            value = ""
        fields[name] = value if name.startswith("password") else value.strip()

    errors = {}
    labels = {
        "first_name": "First name",
        "last_name": "Last name",
        "email": "Email",
        "username": "Username",
        "password": "Password",
        "password_confirm": "Password confirmation",
    }
    for name, label in labels.items():
        if not fields[name]:
            errors[name] = [f"{label} is required."]

    User = get_user_model()

    if fields["email"] and "email" not in errors:
        try:
            validate_email(fields["email"])
        except ValidationError:
            errors["email"] = ["Enter a valid email address."]
        else:
            if User.objects.filter(email__iexact=fields["email"]).exists():
                errors["email"] = ["An account with this email already exists."]

    if fields["username"] and User.objects.filter(username__iexact=fields["username"]).exists():
        errors["username"] = ["This username is already taken."]

    if fields["password"] and fields["password_confirm"] and fields["password"] != fields["password_confirm"]:
        errors["password_confirm"] = ["Passwords do not match."]

    if fields["password"] and "password_confirm" not in errors:
        candidate = User(
            username=fields["username"],
            email=fields["email"],
            first_name=fields["first_name"],
            last_name=fields["last_name"],
        )
        try:
            validate_password(fields["password"], user=candidate)
        except ValidationError as e:
            errors["password"] = list(e.messages)

    if errors:
        first_error = next(iter(errors.values()))[0]
        return JsonResponse({"error": first_error, "errors": errors}, status=400)

    with transaction.atomic():
        user = User.objects.create_user(
            username=fields["username"],
            email=fields["email"],
            password=fields["password"],
            first_name=fields["first_name"],
            last_name=fields["last_name"],
        )
        Inventory.objects.create(owner=user, name="My Inventory")

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse(
        {"authenticated": True, "username": user.get_username()},
        status=201,
    )


@require_POST
def auth_logout(request):
    logout(request)
    return JsonResponse({"authenticated": False})


ACCOUNT_FIELDS = {
    "first_name": "First name",
    "last_name": "Last name",
    "email": "Email",
}


def _account_payload(user):
    return {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "username": user.get_username(),
    }


@require_http_methods(["GET", "PATCH"])
def account_api(request):
    """Read or update the signed-in user's own profile. There is no user id in
    the URL, so one account can never address another."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    user = request.user

    if request.method == "GET":
        return JsonResponse({"success": True, "account": _account_payload(user)})

    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request body."}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({"error": "Expected a JSON object."}, status=400)
    if not data or set(data) - set(ACCOUNT_FIELDS):
        return JsonResponse({
            "error": "Provide only a first name, last name, and/or email to update.",
        }, status=400)

    errors = {}
    fields = {}
    for name, value in data.items():
        if not isinstance(value, str):
            errors[name] = ["Enter text for this field."]
            continue
        fields[name] = value.strip()
        if not fields[name]:
            errors[name] = [f"{ACCOUNT_FIELDS[name]} is required."]

    User = get_user_model()

    if fields.get("email") and "email" not in errors:
        try:
            validate_email(fields["email"])
        except ValidationError:
            errors["email"] = ["Enter a valid email address."]
        else:
            if (
                User.objects
                .filter(email__iexact=fields["email"])
                .exclude(pk=user.pk)
                .exists()
            ):
                errors["email"] = ["An account with this email already exists."]

    if not errors:
        for name, value in fields.items():
            setattr(user, name, value)
        # Field validation enforces the model's max_length for each column.
        try:
            user.clean_fields(exclude=[
                field.name for field in User._meta.fields if field.name not in fields
            ])
        except ValidationError as error:
            errors = error.message_dict

    if errors:
        user.refresh_from_db()
        first_error = next(iter(errors.values()))[0]
        return JsonResponse({"error": first_error, "errors": errors}, status=400)

    user.save(update_fields=list(fields))
    return JsonResponse({"success": True, "account": _account_payload(user)})


@require_POST
def change_password_api(request):
    """Change the signed-in user's password and keep this session signed in.

    update_session_auth_hash() rotates this session's key, so the client must
    store the new session cookie. Other sessions for the user are signed out.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request body."}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({"error": "Expected a JSON object."}, status=400)

    fields = {}
    for name in ("current_password", "new_password", "new_password_confirm"):
        value = data.get(name, "")
        fields[name] = value if isinstance(value, str) else ""

    errors = {}
    labels = {
        "current_password": "Current password",
        "new_password": "New password",
        "new_password_confirm": "Password confirmation",
    }
    for name, label in labels.items():
        if not fields[name]:
            errors[name] = [f"{label} is required."]

    user = request.user

    if fields["current_password"] and not user.check_password(fields["current_password"]):
        errors["current_password"] = ["Your current password is incorrect."]

    if (
        fields["new_password"]
        and fields["new_password_confirm"]
        and fields["new_password"] != fields["new_password_confirm"]
    ):
        errors["new_password_confirm"] = ["Passwords do not match."]

    if fields["new_password"] and not errors:
        if fields["new_password"] == fields["current_password"]:
            errors["new_password"] = [
                "New password must be different from your current password."
            ]
        else:
            try:
                validate_password(fields["new_password"], user=user)
            except ValidationError as e:
                errors["new_password"] = list(e.messages)

    if errors:
        first_error = next(iter(errors.values()))[0]
        return JsonResponse({"error": first_error, "errors": errors}, status=400)

    user.set_password(fields["new_password"])
    user.save(update_fields=["password"])
    update_session_auth_hash(request, user)
    return JsonResponse({"success": True})

ACTIVE_INVENTORY_KEY = "active_inventory_id"

def _lock_inventory_owner(user):
    """Serialize inventory changes for one owner inside transaction.atomic()."""
    User = get_user_model()
    owners = User.objects.filter(pk=user.pk)
    if connection.vendor == "sqlite":
        # SELECT FOR UPDATE has no effect on SQLite. This no-op write takes
        # its writer lock BEFORE reading how many usable inventories remain.
        # No user data changes; a second archive must wait or safely retry.
        pk_field = User._meta.pk.attname
        owners.update(**{pk_field: F(pk_field)})
    else:
        owners.select_for_update().get()


def _inventory_busy_response(error):
    """Turn SQLite write contention into a retryable error, not a failed save."""
    if connection.vendor != "sqlite" or not any(
        word in str(error).lower() for word in ("locked", "busy")
    ):
        raise error
    return JsonResponse({
        "success": False,
        "error": "Your inventories are being updated. Please try again.",
    }, status=409)

    
def _active_inventory(request):
    inventories = Inventory.objects.filter(
        owner=request.user,
        archived_at__isnull=True,
    ).order_by("created_at", "pk")

    saved_id = request.session.get(ACTIVE_INVENTORY_KEY)
    inventory = None

    if saved_id:
        try:
            inventory = inventories.filter(
                public_id=UUID(str(saved_id))
            ).first()
        except (ValueError, TypeError, AttributeError):
            pass

    if inventory is None:
        inventory = inventories.first()

        if inventory:
            request.session[ACTIVE_INVENTORY_KEY] = str(
                inventory.public_id
            )
        else:
            request.session.pop(ACTIVE_INVENTORY_KEY, None)

    return inventory


@require_http_methods(["GET", "POST"])
def inventories_api(request):
    try:
        is_authenticated = request.user.is_authenticated
    except OperationalError as error:
        return _inventory_busy_response(error)
    if not is_authenticated:
        return JsonResponse(
            {"error": "Authentication required."},
            status=401,
        )

    if request.method == "GET":
        active = _active_inventory(request)

        inventories = (
            Inventory.objects
            .filter(
                owner=request.user,
                archived_at__isnull=True,
            )
            .annotate(
                item_count=Count(
                    "items",
                    filter=Q(items__archived_at__isnull=True),
                )
            )
            .order_by("created_at", "pk")
        )

        return JsonResponse({
            "success": True,
            "active_inventory_id": (
                str(active.public_id) if active else None
            ),
            "inventories": [
                {
                    "public_id": str(inv.public_id),
                    "name": inv.name,
                    "description": inv.description,
                    "item_count": inv.item_count,
                }
                for inv in inventories
            ],
        })

    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Invalid JSON."},
            status=400,
        )

    if not isinstance(data, dict):
        return JsonResponse(
            {"error": "Expected a JSON object."},
            status=400,
        )

    fields = {
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "inventory_type": data.get("inventory_type", "personal"),
        "default_currency": data.get("default_currency", "USD"),
    }

    if not all(isinstance(value, str) for value in fields.values()):
        return JsonResponse(
            {"error": "Invalid inventory fields."},
            status=400,
        )

    inventory = Inventory(
        owner=request.user,
        name=fields["name"].strip(),
        description=fields["description"],
        inventory_type=fields["inventory_type"],
        default_currency=fields["default_currency"].upper(),
    )

    try:
        with transaction.atomic():
            _lock_inventory_owner(request.user)
            inventory.full_clean()
            inventory.save()
    except ValidationError as error:
        return JsonResponse({
            "success": False,
            "errors": (
                error.message_dict
                if hasattr(error, "message_dict")
                else {"non_field_errors": error.messages}
            ),
        }, status=400)
    except IntegrityError:
        return JsonResponse(
            {"error": "Inventory could not be created."},
            status=409,
        )
    except OperationalError as error:
        return _inventory_busy_response(error)

    request.session[ACTIVE_INVENTORY_KEY] = str(
        inventory.public_id
    )

    return JsonResponse({
        "success": True,
        "inventory": {
            "public_id": str(inventory.public_id),
            "name": inventory.name,
        },
        "active_inventory_id": str(inventory.public_id),
    }, status=201)


@require_POST
def select_inventory_api(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Authentication required."},
            status=401,
        )

    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Invalid JSON."},
            status=400,
        )

    if not isinstance(data, dict):
        return JsonResponse(
            {"error": "Expected a JSON object."},
            status=400,
        )

    raw_id = data.get("inventory_id")

    try:
        inventory_id = UUID(raw_id) if isinstance(raw_id, str) else None
    except ValueError:
        inventory_id = None

    if inventory_id is None:
        return JsonResponse(
            {"error": "Invalid inventory ID."},
            status=400,
        )

    inventory = Inventory.objects.filter(
        public_id=inventory_id,
        owner=request.user,
        archived_at__isnull=True,
    ).first()

    if inventory is None:
        return JsonResponse(
            {"error": "Inventory not found."},
            status=404,
        )

    request.session[ACTIVE_INVENTORY_KEY] = str(
        inventory.public_id
    )

    return JsonResponse({
        "success": True,
        "active_inventory_id": str(inventory.public_id),
    })

@require_http_methods(["PATCH"])
def update_inventory_api(request, inventory_id):
    """Rename or describe an owned, unarchived inventory without switching it."""
    try:
        is_authenticated = request.user.is_authenticated
    except OperationalError as error:
        return _inventory_busy_response(error)
    if not is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({"error": "Expected a JSON object."}, status=400)
    if not data or set(data) - {"name", "description"}:
        return JsonResponse({
            "error": "Provide only a name and/or description to update.",
        }, status=400)

    errors = {}
    for field, value in data.items():
        if not isinstance(value, str):
            errors[field] = ["Enter text for this field."]
    if "name" in data and isinstance(data["name"], str):
        # Model.clean() runs after field validation, so trim BEFORE full_clean
        # to reject whitespace-only names and validate the stored length.
        data["name"] = data["name"].strip()
        if not data["name"]:
            errors["name"] = ["Inventory name is required."]
    if errors:
        return JsonResponse({"success": False, "errors": errors}, status=400)

    try:
        with transaction.atomic():
            _lock_inventory_owner(request.user)
            inventory = Inventory.objects.filter(
                public_id=inventory_id,
                owner=request.user,
                archived_at__isnull=True,
            ).first()
            if inventory is None:
                return JsonResponse({"error": "Inventory not found."}, status=404)

            for field, value in data.items():
                setattr(inventory, field, value)
            inventory.full_clean()
            inventory.save(update_fields=[*data, "updated_at"])
            active = _active_inventory(request)
    except ValidationError as error:
        return JsonResponse({
            "success": False,
            "errors": (
                error.message_dict
                if hasattr(error, "message_dict")
                else {"non_field_errors": error.messages}
            ),
        }, status=400)
    except IntegrityError:
        return JsonResponse({
            "error": "An active inventory with this name already exists.",
        }, status=409)
    except OperationalError as error:
        return _inventory_busy_response(error)

    return JsonResponse({
        "success": True,
        "inventory": {
            "public_id": str(inventory.public_id),
            "name": inventory.name,
            "description": inventory.description,
        },
        "active_inventory_id": str(active.public_id) if active else None,
    })


@require_POST
def archive_inventory_api(request, inventory_id):
    """Soft-archive an owned inventory, always leaving a usable replacement."""
    try:
        is_authenticated = request.user.is_authenticated
    except OperationalError as error:
        return _inventory_busy_response(error)
    if not is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        with transaction.atomic():
            _lock_inventory_owner(request.user)
            inventories = Inventory.objects.filter(
                owner=request.user,
                archived_at__isnull=True,
            )
            inventory = inventories.filter(public_id=inventory_id).first()
            if inventory is None:
                return JsonResponse({"error": "Inventory not found."}, status=404)
            if not inventories.exclude(pk=inventory.pk).exists():
                return JsonResponse({
                    "success": False,
                    "error": (
                        "You must keep at least one active inventory. "
                        "Create another inventory before archiving this one."
                    ),
                }, status=409)

            inventory.archived_at = timezone.now()
            inventory.save(update_fields=["archived_at", "updated_at"])
            # Reuse the existing selection rules. A valid selected inventory
            # stays selected; an archived/stale selection falls back to the
            # oldest remaining owned inventory (created_at, then pk).
            active = _active_inventory(request)
    except OperationalError as error:
        return _inventory_busy_response(error)

    return JsonResponse({
        "success": True,
        "archived_inventory_id": str(inventory.public_id),
        "active_inventory_id": str(active.public_id),
    })

def dashboard_summary(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    user = request.user
    user_inventory = _active_inventory(request)
    inventory_id = str(user_inventory.public_id) if user_inventory else None

    items = (
        Item.objects
        .select_related("category")
        .filter(
            inventory=user_inventory,
            archived_at__isnull=True,
        )
        .order_by("-updated_at")
    )

    total_items = items.count()
    estimated_value = Decimal("0.00")
    purchase_value = Decimal("0.00")
    category_totals = {}

    recent_items = []

    for item in items:
        current_value = item.effective_value or Decimal("0.00")
        current_purchase = item.purchase_amount or Decimal("0.00")

        estimated_value += current_value
        purchase_value += current_purchase

        category_name = (
            item.category.name
            if item.category
            else "Uncategorized"
        )

        category_totals[category_name] = (
            category_totals.get(
                category_name,
                Decimal("0.00"),
            )
            + current_value
        )

    for item in items[:5]:
        attachment = item.attachments.filter(
            file_type="photo", archived_at__isnull=True,
        ).order_by("-is_primary", "-uploaded_at").first()
        image_url = _attachment_file_url(attachment) if attachment and attachment.file else None

        recent_items.append(
            {
                "public_id": str(item.public_id),
                "name": item.name,
                "category": (
                    item.category.name
                    if item.category
                    else "Uncategorized"
                ),
                "value": float(
                    item.effective_value
                    or Decimal("0.00")
                ),
                "date": item.updated_at.strftime(
                    "%b %d, %Y"
                ).replace(" 0", " "),
                "icon": "inventory_2",
                "image_url": image_url,
            }
        )

    category_data = [
        {
            "name": name,
            "value": float(value),
        }
        for name, value in sorted(
            category_totals.items(),
            key=lambda pair: pair[1],
            reverse=True,
        )
    ]

    payload = {
        "summary": {
            "total_items": total_items,
            "estimated_value": float(estimated_value),
            "purchase_value": float(purchase_value),
            "items_needing_attention": items.filter(
                valuation_date__isnull=True
            ).count(),
        },
        "category_data": category_data,
        "recent_items": recent_items,
        "inventory_id": inventory_id,
    }

    return JsonResponse(payload)


def location_payload(location):
    return {
        "public_id": str(location.public_id),
        "name": location.name,
        "description": location.description,
        "parent_id": str(location.parent.public_id) if location.parent_id else None,
        "path": location.path,
    }


def _location_options(inventory):
    locations = Location.objects.filter(
        inventory=inventory,
        archived_at__isnull=True,
    ).select_related("parent")
    return sorted(
        (location_payload(location) for location in locations),
        key=lambda location: (location["path"].casefold(), location["public_id"]),
    )


def _field_validation_response(error):
    errors = (
        error.message_dict
        if hasattr(error, "message_dict")
        else {"non_field_errors": error.messages}
    )
    first_error = next(iter(errors.values()))[0]
    return JsonResponse({"success": False, "error": first_error, "errors": errors}, status=400)


def _json_object(request):
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValidationError("Invalid JSON request body.")
    if not isinstance(data, dict):
        raise ValidationError("Expected a JSON object.")
    return data


def _item_request_data(request):
    data = _json_object(request) if request.content_type == "application/json" else request.POST
    location = data.get("location")
    if location is not None and not isinstance(location, str):
        raise ValidationError({"location": "Choose an active location in this inventory."})
    return data


def _save_item_form_response(request, inventory, item=None):
    data = _item_request_data(request)
    editing = item is not None
    with transaction.atomic():
        _lock_inventory_owner(request.user)
        inventory = get_object_or_404(
            Inventory, pk=inventory.pk, owner=request.user, archived_at__isnull=True,
        )
        if editing:
            item = get_object_or_404(
                Item.objects.select_related("location"),
                pk=item.pk, inventory=inventory, archived_at__isnull=True,
            )
        form = ItemForm(inventory, data, instance=item)
        if not form.is_valid():
            return JsonResponse({
                'success': False,
                'errors': {field: error[0] for field, error in form.errors.items()},
            }, status=400)
        item = form.save()
        action = "updated" if editing else "added"
        return JsonResponse({
            'success': True,
            'message': f"Item '{item.name}' {action} successfully!",
            'item_id': str(item.public_id),
        })


def _update_location_fields(location, data):
    unknown_fields = set(data) - {"name", "description", "parent_id"}
    if unknown_fields:
        raise ValidationError({
            field: "This field cannot be set on a location."
            for field in sorted(unknown_fields)
        })
    for field in ("name", "description"):
        value = data.get(field, getattr(location, field))
        if not isinstance(value, str):
            raise ValidationError({field: "Enter text for this field."})
        setattr(location, field, value.strip())

    if "parent_id" in data:
        parent_id = data["parent_id"]
        if parent_id is None:
            location.parent = None
        else:
            try:
                if not isinstance(parent_id, str):
                    raise ValueError
                parent_uuid = UUID(parent_id)
            except (ValueError, TypeError, AttributeError):
                raise ValidationError({"parent_id": "Choose an active parent location in this inventory."})
            parent = Location.objects.filter(
                public_id=parent_uuid,
                inventory=location.inventory,
                archived_at__isnull=True,
            ).first()
            if parent is None:
                raise ValidationError({"parent_id": "Choose an active parent location in this inventory."})
            location.parent = parent

    try:
        location.full_clean()
    except ValidationError as error:
        errors = error.message_dict if hasattr(error, "message_dict") else {"non_field_errors": error.messages}
        if "parent" in errors:
            errors["parent_id"] = errors.pop("parent")
        raise ValidationError(errors) from error


@require_http_methods(["GET", "POST"])
def location_list_api(request, inventory_id):
    """List or create active locations within one owned, active inventory."""
    try:
        authenticated = request.user.is_authenticated
    except OperationalError as error:
        return _inventory_busy_response(error)
    if not authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        if request.method == "GET":
            inventory = get_object_or_404(
                Inventory, public_id=inventory_id,
                owner=request.user, archived_at__isnull=True,
            )
            return JsonResponse({
                "success": True,
                "inventory": {"public_id": str(inventory.public_id), "name": inventory.name},
                "locations": _location_options(inventory),
            })

        data = _json_object(request)
        with transaction.atomic():
            # The same owner lock protects parent changes, archive checks, and
            # item assignment so a concurrent save cannot bypass those checks.
            _lock_inventory_owner(request.user)
            inventory = get_object_or_404(
                Inventory, public_id=inventory_id,
                owner=request.user, archived_at__isnull=True,
            )
            location = Location(inventory=inventory)
            _update_location_fields(location, data)
            location.save()
            payload = location_payload(location)
        return JsonResponse({"success": True, "location": payload}, status=201)
    except Http404:
        return JsonResponse({"success": False, "error": "Inventory not found."}, status=404)
    except ValidationError as error:
        return _field_validation_response(error)
    except IntegrityError:
        return JsonResponse({"success": False, "error": "A location with this name already exists here."}, status=409)
    except OperationalError as error:
        return _inventory_busy_response(error)


@require_http_methods(["PATCH", "DELETE"])
def location_detail_api(request, location_id):
    """Edit a location or archive an empty location without moving belongings."""
    try:
        authenticated = request.user.is_authenticated
    except OperationalError as error:
        return _inventory_busy_response(error)
    if not authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        data = _json_object(request) if request.method == "PATCH" else None
        with transaction.atomic():
            _lock_inventory_owner(request.user)
            location = get_object_or_404(
                Location.objects.select_related("inventory", "parent"),
                public_id=location_id,
                inventory__owner=request.user,
                inventory__archived_at__isnull=True,
                archived_at__isnull=True,
            )
            if request.method == "DELETE":
                if location.sub_locations.filter(archived_at__isnull=True).exists():
                    raise ValidationError("Move or archive this location's child locations before archiving it.")
                if location.items.filter(archived_at__isnull=True).exists():
                    raise ValidationError("Move or unassign the items in this location before archiving it.")
                location.archived_at = timezone.now()
                location.save(update_fields=["archived_at", "updated_at"])
                return JsonResponse({"success": True, "message": "Location archived."})

            _update_location_fields(location, data)
            location.save()
            payload = location_payload(location)
        return JsonResponse({"success": True, "location": payload})
    except Http404:
        return JsonResponse({"success": False, "error": "Location not found."}, status=404)
    except ValidationError as error:
        return _field_validation_response(error)
    except IntegrityError:
        return JsonResponse({"success": False, "error": "A location with this name already exists here."}, status=409)
    except OperationalError as error:
        return _inventory_busy_response(error)


def _filter_items_by_location(items, inventory, value):
    if not value:
        return items
    if value == "unassigned":
        return items.filter(location__isnull=True)
    try:
        location_id = UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ValidationError({"location": "Choose an active location in this inventory."})
    location = Location.objects.filter(
        public_id=location_id, inventory=inventory, archived_at__isnull=True,
    ).first()
    if location is None:
        raise ValidationError({"location": "Choose an active location in this inventory."})
    return items.filter(location=location)


def item_list(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Authentication required."},
            status=401
        )

    active_inventory = _active_inventory(request)

    items = (
        Item.objects
        .select_related(
            "inventory",
            "category",
            "location",
        )
        .filter(
            inventory=active_inventory,
            archived_at__isnull=True,
        )
        .order_by("-updated_at")
    )

    try:
        items = _filter_items_by_location(items, active_inventory, request.GET.get("location"))
    except ValidationError as error:
        return _field_validation_response(error)

    payload = {
        "items": [
            {
                "public_id": str(item.public_id),
                "name": item.name,
                "inventory": item.inventory.name,
                "category": (
                    item.category.name
                    if item.category
                    else None
                ),
                "location": (
                    item.location.path
                    if item.location
                    else None
                ),
                "location_id": str(item.location.public_id) if item.location_id else None,
                "quantity": item.quantity,
                "condition": item.condition,
                "purchase_value": (
                    float(item.purchase_amount)
                    if item.purchase_amount is not None
                    else None
                ),
                "estimated_value": (
                    float(item.effective_value)
                    if item.effective_value is not None
                    else None
                ),
                "effective_value": (
                    str(item.effective_value)
                    if item.effective_value is not None
                    else None
                ),
                "effective_value_source": item.effective_value_source,
                "updated_at": item.updated_at.isoformat(),
            }
            for item in items
        ]
    }

    return JsonResponse(payload)

@require_http_methods(["GET", "POST"])
def add_item_api(request, inventory_id):
    """API endpoint for adding a new item to an inventory"""
    try:
        authenticated = request.user.is_authenticated
    except OperationalError as error:
        return _inventory_busy_response(error)
    if not authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        current_user = request.user
        # Get the inventory and check ownership
        inventory = get_object_or_404(Inventory, public_id=inventory_id, archived_at__isnull=True,)

        if inventory.owner != current_user:
            return JsonResponse(
                {'success': False, 'error': 'You can only add items to your own inventory.'},
                status=403
            )
        
        if request.method == 'GET':
            categories = Category.objects.filter(
                inventory=inventory,
                archived_at__isnull=True,
            ).values('id', 'name') # Make sure to grab id and name

            return JsonResponse({
                'success': True,
                'inventory': {
                    'public_id': inventory.public_id,
                    'name': inventory.name,
                },
                'categories': list(categories),
                'locations': _location_options(inventory),
            })
        
        if request.method == 'POST':
            return _save_item_form_response(request, inventory)
    
    except Http404:
        return JsonResponse({
            'success': False,
            'error': 'Not found.',
        }, status=404)
    except ValidationError as error:
        return _field_validation_response(error)
    except OperationalError as error:
        return _inventory_busy_response(error)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

@require_http_methods(["GET", "POST", "DELETE"])
def edit_item_api(request, item_id):
    """API endpoint for editing an existing item"""
    try:
        authenticated = request.user.is_authenticated
    except OperationalError as error:
        return _inventory_busy_response(error)
    if not authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        # Exclude archived items and items in archived inventories.
        item = get_object_or_404(
            Item,
            public_id=item_id,
            archived_at__isnull=True,
            inventory__archived_at__isnull=True,
        )
        current_user = request.user
        if item.inventory.owner != current_user:
            return JsonResponse(
                {'success': False, 'error': 'You can only edit items in your own inventory.'},
                status=403
            )
        
        if request.method == 'GET':
            # Return item data and available categories
            categories = Category.objects.filter(
                inventory=item.inventory,
                archived_at__isnull=True,
            ).values('id', 'public_id', 'name')
            
            return JsonResponse({
                'success': True,
                'item': {
                    'public_id': str(item.public_id),
                    'name': item.name,
                    'inventory_id': str(item.inventory.public_id),  # <--- Add this line here!
                    'category_id': item.category.id if item.category else None,
                    'location_id': str(item.location.public_id) if item.location_id else None,
                    'location': item.location.path if item.location_id else None,
                    'description': item.description,
                    'brand': item.brand,
                    'model_number': item.model_number,
                    'serial_number': item.serial_number,
                    'condition': item.condition,
                    'quantity': item.quantity,
                    'purchase_date': item.purchase_date.isoformat() if item.purchase_date else None,
                    'purchase_amount': str(item.purchase_amount) if item.purchase_amount is not None else None,
                    'manual_value': str(item.manual_value) if item.manual_value is not None else None,
                    'current_estimated_amount': str(item.current_estimated_amount) if item.current_estimated_amount is not None else None,
                    'effective_value': str(item.effective_value) if item.effective_value is not None else None,
                    'effective_value_source': item.effective_value_source,
                    'notes': item.notes,
                },
                'categories': list(categories),
                'locations': _location_options(item.inventory),
            })
        
        if request.method == 'POST':
            return _save_item_form_response(request, item.inventory, item)

        if request.method == 'DELETE':
            item.archived_at = timezone.now()
            item.save(update_fields=['archived_at', 'updated_at'])
            return JsonResponse({
                'success': True,
                'message': f"Item '{item.name}' was deleted successfully.",
            })
    
    except Http404:
        return JsonResponse({
            'success': False,
            'error': 'Not found.',
        }, status=404)
    except ValidationError as error:
        return _field_validation_response(error)
    except OperationalError as error:
        return _inventory_busy_response(error)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

@require_http_methods(["GET"])
def inventory_detail_api(request, inventory_id):
    """API endpoint for getting all items in an inventory"""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        current_user = request.user
        inventory = get_object_or_404(Inventory, public_id=inventory_id, archived_at__isnull=True,)        
        if inventory.owner != current_user:
            return JsonResponse(
                {'success': False, 'error': 'You don\'t have access to this inventory.'},
                status=403
            )
        
        items = inventory.items.filter(archived_at__isnull=True).select_related('category', 'location').order_by('-updated_at')
        items = _filter_items_by_location(items, inventory, request.GET.get('location'))

        items_data = []
        for item in items:
            primary_photo = item.attachments.filter(
                file_type='photo',
                archived_at__isnull=True
            ).order_by('-is_primary', '-uploaded_at').first()

            items_data.append({
                'public_id': str(item.public_id),
                'name': item.name,
                'category': item.category.name if item.category else 'Uncategorized',
                'location': item.location.path if item.location else None,
                'location_id': str(item.location.public_id) if item.location_id else None,
                'condition': item.get_condition_display(),
                'purchase_amount': str(item.purchase_amount) if item.purchase_amount is not None else None,
                'current_estimated_amount': str(item.current_estimated_amount) if item.current_estimated_amount is not None else None,
                'manual_value': str(item.manual_value) if item.manual_value is not None else None,
                'effective_value': str(item.effective_value) if item.effective_value is not None else None,
                'effective_value_source': item.effective_value_source,
                'primary_photo_url': _attachment_file_url(primary_photo) if primary_photo and primary_photo.file else None,
            })

        return JsonResponse({
            'success': True,
            'inventory': {
                'public_id': str(inventory.public_id),
                'name': inventory.name,
                'description': inventory.description,
            },
            'items': items_data,
        })
    
    except Http404:
        return JsonResponse({
            'success': False,
            'error': 'Not found.',
        }, status=404)
    except ValidationError as error:
        return _field_validation_response(error)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

@require_http_methods(["GET"])
def item_detail_api(request, item_id):
    """API endpoint for getting a single item's details."""

    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Authentication required."},
            status=401,
        )

    try:
        item = get_object_or_404(
            Item.objects.select_related(
                "inventory",
                "category",
                "location",
            ),
            public_id=item_id,
            inventory__owner=request.user,
            inventory__archived_at__isnull=True,
            archived_at__isnull=True,
        )

        return JsonResponse(
            {
                "success": True,
                "item": {
                    "public_id": str(item.public_id),
                    "name": item.name,
                    "category": (
                        item.category.name
                        if item.category
                        else "Uncategorized"
                    ),
                    "location": (
                        item.location.path
                        if item.location
                        else None
                    ),
                    "location_id": str(item.location.public_id) if item.location_id else None,
                    "description": item.description,
                    "brand": item.brand,
                    "model_number": item.model_number,
                    "serial_number": item.serial_number,
                    "condition": item.get_condition_display(),
                    "condition_code": item.condition,
                    "quantity": item.quantity,
                    "purchase_date": (
                        item.purchase_date.isoformat()
                        if item.purchase_date
                        else None
                    ),
                    "purchase_amount": (
                        str(item.purchase_amount)
                        if item.purchase_amount is not None
                        else None
                    ),
                    "current_estimated_amount": (
                        str(item.current_estimated_amount)
                        if item.current_estimated_amount is not None
                        else None
                    ),
                    "manual_value": (
                        str(item.manual_value)
                        if item.manual_value is not None
                        else None
                    ),
                    "effective_value": (
                        str(item.effective_value)
                        if item.effective_value is not None
                        else None
                    ),
                    "effective_value_source": item.effective_value_source,
                    "valuation_date": (
                        item.valuation_date.isoformat()
                        if item.valuation_date
                        else None
                    ),
                    "notes": item.notes,
                    "created_at": item.created_at.isoformat(),
                    "updated_at": item.updated_at.isoformat(),
                },
                "inventory": {
                    "public_id": str(
                        item.inventory.public_id
                    ),
                    "name": item.inventory.name,
                },
            }
        )

    except Http404:
        return JsonResponse(
            {
                "success": False,
                "error": "Item not found.",
            },
            status=404,
        )

@require_http_methods(["GET", "POST"])
def item_attachments_api(request, item_id):
    """API endpoint to list or upload attachments for an item."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    item = Item.objects.filter(
        public_id=item_id,
        archived_at__isnull=True,
        inventory__archived_at__isnull=True,
    ).first()
    if item is None:
        return JsonResponse({"success": False, "error": "Item not found."}, status=404)
    if item.inventory.owner != request.user:
        return JsonResponse({"success": False, "error": "Access denied."}, status=403)

    if request.method == "GET":
        attachments = item.attachments.filter(archived_at__isnull=True).order_by("-uploaded_at")
        return JsonResponse({
            "success": True,
            "attachments": [
                {
                    "public_id": str(att.public_id),
                    "file_type": att.file_type,
                    "file_url": _attachment_file_url(att) if att.file else "",
                    "original_filename": att.original_filename,
                    "file_size": att.file_size,
                    "is_primary": att.is_primary,
                    "uploaded_at": att.uploaded_at.isoformat(),
                }
                for att in attachments
            ]
        })

    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        file_type = request.POST.get("file_type", "photo")

        if not uploaded_file:
            return JsonResponse({"success": False, "error": "No file uploaded."}, status=400)

        if file_type not in AttachmentType.values:
            return JsonResponse({"success": False, "error": "Invalid file type."}, status=400)

        attachment = Attachment.objects.create(
            item=item,
            file=uploaded_file,
            file_type=file_type,
            original_filename=uploaded_file.name,
            mime_type=getattr(uploaded_file, "content_type", ""),
            file_size=uploaded_file.size,
            is_primary=(file_type == "photo" and not item.attachments.filter(file_type="photo", archived_at__isnull=True).exists()),
        )

        return JsonResponse({
            "success": True,
            "message": "File uploaded successfully.",
            "attachment": {
                "public_id": str(attachment.public_id),
                "file_type": attachment.file_type,
                "file_url": _attachment_file_url(attachment),
                "original_filename": attachment.original_filename,
            }
        }, status=201)


def _attachment_content_type(header):
    """Only common raster images and PDFs are eligible for inline display.

    Inspect bytes instead of trusting the uploaded filename or MIME metadata.
    HTML, SVG and other formats remain ordinary downloads.
    """
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    if header.startswith(b"%PDF-"):
        return "application/pdf"
    return "application/octet-stream"


@require_http_methods(["GET", "HEAD"])
def attachment_file_api(request, attachment_id):
    """Serve an owned attachment while respecting all three archive levels."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    attachment = Attachment.objects.filter(
        public_id=attachment_id,
        item__inventory__owner=request.user,
        archived_at__isnull=True,
        item__archived_at__isnull=True,
        item__inventory__archived_at__isnull=True,
    ).first()
    if attachment is None or not attachment.file:
        return JsonResponse({"error": "Attachment not found."}, status=404)

    try:
        opened_file = attachment.file.open("rb")
        content_type = _attachment_content_type(opened_file.read(16))
        opened_file.seek(0)
    except (OSError, ValueError):
        attachment.file.close()
        return JsonResponse({"error": "File not found."}, status=404)

    response = FileResponse(
        opened_file,
        content_type=content_type,
        as_attachment=(content_type == "application/octet-stream"),
        filename=attachment.original_filename or attachment.file.name.rsplit("/", 1)[-1],
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@require_http_methods(["DELETE"])
def attachment_detail_api(request, attachment_id):
    """API endpoint to delete/archive an attachment."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    attachment = Attachment.objects.filter(
        public_id=attachment_id,
        archived_at__isnull=True,
        item__archived_at__isnull=True,
        item__inventory__archived_at__isnull=True,
    ).first()
    if attachment is None:
        return JsonResponse({"success": False, "error": "Attachment not found."}, status=404)
    if attachment.item.inventory.owner != request.user:
        return JsonResponse({"success": False, "error": "Access denied."}, status=403)

    attachment.archived_at = timezone.now()
    attachment.save(update_fields=["archived_at"])

    return JsonResponse({"success": True, "message": "Attachment deleted successfully."})

@require_POST
def item_valuation_api(request, item_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)
    item = Item.objects.filter(
        public_id=item_id,
        inventory__owner=request.user,
        archived_at__isnull=True,
        inventory__archived_at__isnull=True,
    ).first()
    if item is None:
        return JsonResponse({"error": "Item not found."}, status=404)
    query = " ".join(
        part.strip()
        for part in [item.name, item.brand, item.model_number]
        if part and part.strip()
    )
    condition = (
        "new"
        if item.condition == "new"
        else "used"
    )
    try: 
        rows = search_ebay(query)
        result = estimate(rows, query, want_condition=condition)
    # ValueError / KeyError: eBay answered, but not with the listing JSON we expect.
    except (requests.exceptions.RequestException, RuntimeError, ValueError, KeyError):
        return JsonResponse({"error": "Unable to retrieve eBay listings"}, status=502,)
    
    valuation_run = None

    if result["estimate"] is not None:
        valuation_run = ValuationRun.objects.create(
            item=item,
            requested_by=request.user,
            valuation_type="automated",
            status="success",
            estimated_amount=Decimal(str(result["estimate"])),
            currency="USD",
            range_low=(
                Decimal(str(result["low"]))
                if result.get("low") is not None
                else None
            ),
            range_high=(
                Decimal(str(result["high"]))
                if result.get("high") is not None
                else None
            ),
            sample_count=result["n"],
            algorithm_version="poc_v1",
            input_snapshot={
                "query": query,
                "condition": condition,
                "source": "ebay",
                "confidence": result["confidence"],
            },
            started_at=timezone.now(),
            completed_at=timezone.now(),
        )
        source_result = ValuationSourceResult.objects.create(
        valuation_run=valuation_run,
        source="ebay",
        status="success",
        results_found=len(rows),
        results_used=result["n"],
        source_estimate=Decimal(str(result["estimate"])),
        currency="USD",
        )

        for listing in result["comparables"]:
            ComparableListing.objects.create(
            source_result=source_result,
            external_listing_id=listing.listing_id,
            url=listing.url,
            title=listing.title,
            price=listing.price,
            currency="USD",
            condition_normalized=listing.condition or "",
            included_in_estimate=True,
        )

    return JsonResponse({
        "item_id": str(item.public_id),
        "item_name": item.name,
        "query": query,
        "estimate": result["estimate"],
        "range_low": result.get("low"),
        "range_high": result.get("high"),
        "sample_count": result["n"],
        "confidence": result["confidence"],
        "source": "ebay",
        "currency": "USD",
        "valuation_run_id": (
            str(valuation_run.public_id)
            if valuation_run is not None
            else None
        ),
    })

@require_GET
def item_valuation_history_api(request, item_id):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Authentication required."},
            status=401,
        )

    item = Item.objects.filter(
        public_id=item_id,
        inventory__owner=request.user,
        archived_at__isnull=True,
        inventory__archived_at__isnull=True,
    ).first()
    if item is None:
        return JsonResponse({"error": "Item not found."}, status=404)

    runs = (
        ValuationRun.objects
        .filter(item=item)
        .order_by("-requested_at")
    )

    history = []

    for run in runs:
        comparables = []
        for source in run.source_results.all():
            for listing in source.comparable_listings.all():
                comparables.append({
                    "title": listing.title,
                    "price": float(listing.price) if listing.price is not None else None,
                    "url": listing.url,
                    "listing_id": listing.external_listing_id,
                    "condition": listing.condition_normalized,
                })
        history.append({
            "valuation_run_id": str(run.public_id),
            "estimate": (
                float(run.estimated_amount)
                if run.estimated_amount is not None
                else None
            ),
            "range_low": (
                float(run.range_low)
                if run.range_low is not None
                else None
            ),
            "range_high": (
                float(run.range_high)
                if run.range_high is not None
                else None
            ),
            "sample_count": run.sample_count,
            "status": run.status,
            "requested_at": run.requested_at.isoformat(),
            "comparables": comparables,
        })

    return JsonResponse({
        "item_id": str(item.public_id),
        "item_name": item.name,
        "history": history,
    })

@require_POST
def accept_valuation_api(request, item_id):
    try:
        authenticated = request.user.is_authenticated
    except OperationalError as error:
        return _inventory_busy_response(error)
    if not authenticated:
        return JsonResponse(
            {"error": "Authentication required."},
            status=401,
        )

    try:
        data = json.loads(request.body)
        run_id = data.get("valuation_run_id")
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return JsonResponse(
            {"error": "Invalid JSON request."},
            status=400,
        )

    if not run_id:
        return JsonResponse(
            {"error": "valuation_run_id is required."},
            status=400,
        )

    try:
        run_id = UUID(str(run_id))
    except ValueError:
        return JsonResponse(
            {"error": "Invalid valuation_run_id."},
            status=400,
        )

    try:
        with transaction.atomic():
            # Match item-form writes and inventory archive: re-read only after
            # taking the owner lock so acceptance does not use stale values.
            _lock_inventory_owner(request.user)
            item = Item.objects.filter(
                public_id=item_id,
                inventory__owner=request.user,
                inventory__archived_at__isnull=True,
                archived_at__isnull=True,
            ).first()

            if item is None:
                return JsonResponse({"error": "Item not found."}, status=404)

            valuation_run = ValuationRun.objects.filter(
                public_id=run_id,
                item=item,
                status="success",
            ).first()

            if valuation_run is None:
                return JsonResponse({"error": "Valuation not found."}, status=404)

            if valuation_run.estimated_amount is None:
                return JsonResponse(
                    {"error": "This valuation has no estimate."},
                    status=400,
                )

            # Accept is an explicit choice to use this estimate instead of the
            # previous manual override, including defaults saved by older clients.
            item.current_estimated_amount = valuation_run.estimated_amount
            item.manual_value = None
            item.valuation_date = timezone.now()
            item.save(
                update_fields=[
                    "current_estimated_amount",
                    "manual_value",
                    "valuation_date",
                    "updated_at",
                ]
            )

            return JsonResponse({
                "success": True,
                "item_id": str(item.public_id),
                "estimated_value": float(item.effective_value),
                "effective_value": str(item.effective_value),
                "effective_value_source": item.effective_value_source,
                "manual_value": None,
                "valuation_run_id": str(valuation_run.public_id),
                "valuation_date": item.valuation_date.isoformat(),
            })
    except OperationalError as error:
        return _inventory_busy_response(error)


def category_payload(category):
    items = list(
        category.items.filter(archived_at__isnull=True).order_by("-updated_at")
    )

    total_value = sum(
        (item.effective_value if item.effective_value is not None else Decimal("0.00"))
        for item in items
    )

    latest_item_update = items[0].updated_at if items else None

    updated_at = category.updated_at

    if latest_item_update is not None and latest_item_update > updated_at:
        updated_at = latest_item_update

    return {
        "public_id": str(category.public_id),
        "name": category.name,
        "description": category.description,
        "item_count": len(items),
        "total_value": float(total_value),
        "updated_at": updated_at.isoformat(),
    }


@require_http_methods(["GET", "POST"])
def category_list_api(request, inventory_id):
    """
    GET:
        Return all active categories for one inventory.

    POST:
        Create a new category in that inventory.
    """

    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Authentication required."},
            status=401,
        )

    inventory = get_object_or_404(
        Inventory,
        public_id=inventory_id,
        archived_at__isnull=True,
    )

    if inventory.owner != request.user:
        return JsonResponse(
            {
                "success": False,
                "error": ("You can only manage categories " "for your own inventory."),
            },
            status=403,
        )

    if request.method == "GET":

        categories = Category.objects.filter(
            inventory=inventory,
            archived_at__isnull=True,
        ).order_by("name")

        return JsonResponse(
            {
                "success": True,
                "inventory": {
                    "public_id": str(inventory.public_id),
                    "name": inventory.name,
                },
                "categories": [category_payload(category) for category in categories],
            }
        )

    try:
        payload = json.loads(request.body or b"{}")
    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid request body.",
            },
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse({"success": False, "error": "Expected a JSON object."}, status=400)

    name = str(payload.get("name", "")).strip()

    description = str(payload.get("description", "")).strip()

    if not name:
        return JsonResponse(
            {
                "success": False,
                "errors": {
                    "name": "Category name is required.",
                },
            },
            status=400,
        )

    category = Category(
        inventory=inventory,
        name=name,
        description=description,
    )

    try:
        category.full_clean()
        category.save()

    except ValidationError as error:

        errors = (
            error.message_dict
            if hasattr(error, "message_dict")
            else {"category": error.messages}
        )

        return JsonResponse(
            {
                "success": False,
                "errors": errors,
            },
            status=400,
        )

    return JsonResponse(
        {
            "success": True,
            "category": category_payload(category),
        },
        status=201,
    )


@require_http_methods(["GET", "PUT", "DELETE"])
def category_detail_api(
    request,
    category_id,
):
    """
    GET:
        Return one category.

    PUT:
        Update its name / description.

    DELETE:
        Archive the category and move its
        active items to Uncategorized.
    """

    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Authentication required."},
            status=401,
        )

    category = get_object_or_404(
        Category,
        public_id=category_id,
        inventory__archived_at__isnull=True,
        archived_at__isnull=True,
    )

    if category.inventory.owner != request.user:

        return JsonResponse(
            {
                "success": False,
                "error": ("You can only manage categories " "for your own inventory."),
            },
            status=403,
        )

    if request.method == "GET":

        return JsonResponse(
            {
                "success": True,
                "category": category_payload(category),
            }
        )

    if request.method == "DELETE":

        affected_items = category.items.filter(archived_at__isnull=True).count()

        category.items.filter(archived_at__isnull=True).update(category=None)

        category.archived_at = timezone.now()

        category.save(
            update_fields=[
                "archived_at",
                "updated_at",
            ]
        )

        return JsonResponse(
            {
                "success": True,
                "message": (f'Category "{category.name}" ' "was deleted."),
                "items_uncategorized": (affected_items),
            }
        )

    try:
        payload = json.loads(request.body or b"{}")
    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid request body.",
            },
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse({"success": False, "error": "Expected a JSON object."}, status=400)

    name = str(
        payload.get(
            "name",
            category.name,
        )
    ).strip()

    description = str(
        payload.get(
            "description",
            category.description,
        )
    ).strip()

    if not name:

        return JsonResponse(
            {
                "success": False,
                "errors": {
                    "name": ("Category name " "is required."),
                },
            },
            status=400,
        )

    category.name = name
    category.description = description

    try:
        category.full_clean()
        category.save()

    except ValidationError as error:

        errors = (
            error.message_dict
            if hasattr(error, "message_dict")
            else {"category": error.messages}
        )

        return JsonResponse(
            {
                "success": False,
                "errors": errors,
            },
            status=400,
        )

    return JsonResponse(
        {
            "success": True,
            "category": category_payload(category),
        }
    )
