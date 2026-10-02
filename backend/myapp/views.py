import json
from decimal import Decimal

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST

from myapp.forms import ItemForm
from myapp.models import Category, Inventory, Item


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
def auth_logout(request):
    logout(request)
    return JsonResponse({"authenticated": False})


def dashboard_summary(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    user = request.user
    user_inventory = Inventory.objects.filter(
        owner=user,
        archived_at__isnull=True,
    ).first()
    inventory_id = str(user_inventory.public_id) if user_inventory else None

    items = (
        Item.objects
        .select_related("category")
        .filter(
            inventory__owner=request.user,
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


def item_list(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    items = (
        Item.objects
        .select_related(
            "inventory",
            "category",
            "location",
        )
        .filter(
            inventory__owner=request.user,
            archived_at__isnull=True,
        )
        .order_by("-updated_at")
    )

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
                    item.location.name
                    if item.location
                    else None
                ),
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
                "updated_at": item.updated_at.isoformat(),
            }
            for item in items
        ]
    }

    return JsonResponse(payload)

@require_http_methods(["GET", "POST"])
def add_item_api(request, inventory_id):
    """API endpoint for adding a new item to an inventory"""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        current_user = request.user
        # Get the inventory and check ownership
        inventory = get_object_or_404(Inventory, public_id=inventory_id)
        
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
            })
        
        if request.method == 'POST':
            # Parse form data from NiceGUI
            try:
                data = request.POST
            except:
                data = json.loads(request.body)
            
            # Create form with data
            form = ItemForm(inventory, data)
            
            if form.is_valid():
                item = form.save(commit=False)
                item.inventory = inventory
                item.save()
                
                return JsonResponse({
                    'success': True,
                    'message': f"Item '{item.name}' added successfully!",
                    'item_id': str(item.public_id),
                })
            else:
                # Return form errors
                errors = {field: error[0] for field, error in form.errors.items()}
                return JsonResponse({
                    'success': False,
                    'errors': errors,
                }, status=400)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)
 
@require_http_methods(["GET", "POST"])
def edit_item_api(request, item_id):
    """API endpoint for editing an existing item"""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        # Get the item and check ownership
        item = get_object_or_404(Item, public_id=item_id)
        
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
                    'description': item.description,
                    'brand': item.brand,
                    'model_number': item.model_number,
                    'serial_number': item.serial_number,
                    'condition': item.condition,
                    'quantity': item.quantity,
                    'purchase_date': item.purchase_date.isoformat() if item.purchase_date else None,
                    'purchase_amount': str(item.purchase_amount) if item.purchase_amount else None,
                    'manual_value': str(item.manual_value) if item.manual_value else None,
                    'notes': item.notes,
                },
                'categories': list(categories),
            })
        
        if request.method == 'POST':
            # Parse form data from NiceGUI
            try:
                data = request.POST
            except:
                data = json.loads(request.body)
            
            # Create form with data and instance
            form = ItemForm(item.inventory, data, instance=item)
            
            if form.is_valid():
                form.save()
                
                return JsonResponse({
                    'success': True,
                    'message': f"Item '{item.name}' updated successfully!",
                    'item_id': str(item.public_id),
                })
            else:
                # Return form errors
                errors = {field: error[0] for field, error in form.errors.items()}
                return JsonResponse({
                    'success': False,
                    'errors': errors,
                }, status=400)
    
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
        inventory = get_object_or_404(Inventory, public_id=inventory_id)
        
        if inventory.owner != current_user:
            return JsonResponse(
                {'success': False, 'error': 'You don\'t have access to this inventory.'},
                status=403
            )
        
        items = inventory.items.filter(archived_at__isnull=True).order_by('-updated_at')
        
        items_data = [
            {
                'public_id': str(item.public_id),
                'name': item.name,
                'category': item.category.name if item.category else 'Uncategorized',
                'condition': item.get_condition_display(),
                'purchase_amount': str(item.purchase_amount) if item.purchase_amount else None,
                'current_estimated_amount': str(item.current_estimated_amount) if item.current_estimated_amount else None,
                'manual_value': str(item.manual_value) if item.manual_value else None,
            }
            for item in items
        ]
        
        return JsonResponse({
            'success': True,
            'inventory': {
                'public_id': str(inventory.public_id),
                'name': inventory.name,
                'description': inventory.description,
            },
            'items': items_data,
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)
 
@require_http_methods(["GET"])
def item_detail_api(request, item_id):
    """API endpoint for getting a single item's details"""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        item = get_object_or_404(Item, public_id=item_id)

        current_user = request.user
        if item.inventory.owner != current_user:
            return JsonResponse(
                {'success': False, 'error': 'You don\'t have access to this item.'},
                status=403
            )
        
        return JsonResponse({
            'success': True,
            'item': {
                'public_id': str(item.public_id),
                'name': item.name,
                'category': item.category.name if item.category else 'Uncategorized',
                'description': item.description,
                'brand': item.brand,
                'model_number': item.model_number,
                'serial_number': item.serial_number,
                'condition': item.get_condition_display(),
                'quantity': item.quantity,
                'purchase_date': item.purchase_date.isoformat() if item.purchase_date else None,
                'purchase_amount': str(item.purchase_amount) if item.purchase_amount else None,
                'current_estimated_amount': str(item.current_estimated_amount) if item.current_estimated_amount else None,
                'manual_value': str(item.manual_value) if item.manual_value else None,
                'notes': item.notes,
                'created_at': item.created_at.isoformat(),
                'updated_at': item.updated_at.isoformat(),
            },
            'inventory': {
                'public_id': str(item.inventory.public_id),
                'name': item.inventory.name,
            },
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)