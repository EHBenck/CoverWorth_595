import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

# CHOICES

class InventoryType(models.TextChoices):
    PERSONAL = "personal", "Personal"
    HOME = "home", "Home"
    BUSINESS = "business", "Business"
    ESTATE = "estate", "Estate"
    COLLECTION = "collection", "Collection"
    OTHER = "other", "Other"


class ItemCondition(models.TextChoices):
    NEW = "new", "New"
    LIKE_NEW = "like_new", "Like New"
    USED = "used", "Used"
    DAMAGED = "damaged", "Damaged"
    UNKNOWN = "unknown", "Unknown"


class AttachmentType(models.TextChoices):
    PHOTO = "photo", "Photo"
    RECEIPT = "receipt", "Receipt"
    WARRANTY = "warranty", "Warranty"
    APPRAISAL = "appraisal", "Appraisal"
    OTHER = "other", "Other"


class ValuationType(models.TextChoices):
    AUTOMATED = "automated", "Automated"
    MANUAL = "manual", "Manual"
    APPRAISAL = "appraisal", "Appraisal"


class ValuationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    PARTIAL = "partial", "Partial"
    FAILED = "failed", "Failed"


class SourceStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


# INVENTORY

class Inventory(models.Model):
    """
    A top-level collection of belongings owned by one Django user.

    Django keeps the normal integer `id` as the internal primary key.
    `public_id` is the opaque identifier exposed through the API/UI.
    """

    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventories",
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    default_currency = models.CharField(max_length=3, default="USD")

    inventory_type = models.CharField(
        max_length=20,
        choices=InventoryType.choices,
        default=InventoryType.PERSONAL,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                condition=Q(archived_at__isnull=True),
                name="unique_active_inventory_name",
            ),
        ]
        indexes = [
            models.Index(
                fields=["owner", "archived_at"],
                name="inv_owner_arch_idx",
            ),
        ]

    def clean(self):
        super().clean()
        self.name = self.name.strip()

        duplicate = (
            Inventory.objects
            .filter(
                owner=self.owner,
                archived_at__isnull=True,
                name__iexact=self.name,
            )
            .exclude(pk=self.pk)
        )
        if duplicate.exists():
            raise ValidationError(
                {"name": "You already have an active inventory with this name."}
            )

    def __str__(self):
        return self.name

# CATEGORY

class Category(models.Model):
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    inventory = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        related_name="categories",
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["inventory", "name"],
                condition=Q(archived_at__isnull=True),
                name="unique_active_category",
            ),
        ]

    def clean(self):
        super().clean()
        self.name = self.name.strip()

        duplicate = (
            Category.objects
            .filter(
                inventory=self.inventory,
                archived_at__isnull=True,
                name__iexact=self.name,
            )
            .exclude(pk=self.pk)
        )
        if duplicate.exists():
            raise ValidationError(
                {"name": "This category already exists in the inventory."}
            )

    def __str__(self):
        return self.name

# LOCATION

class Location(models.Model):
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    inventory = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        related_name="locations",
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_locations",
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["inventory", "name"],
                condition=Q(
                    parent__isnull=True,
                    archived_at__isnull=True,
                ),
                name="unique_active_root_location",
            ),
            models.UniqueConstraint(
                fields=["inventory", "parent", "name"],
                condition=Q(
                    parent__isnull=False,
                    archived_at__isnull=True,
                ),
                name="unique_active_child_location",
            ),
        ]

    def clean(self):
        super().clean()
        self.name = self.name.strip()

        if self.pk and self.parent_id == self.pk:
            raise ValidationError(
                {"parent": "A location cannot be its own parent."}
            )

        if self.parent_id and self.parent.inventory_id != self.inventory_id:
            raise ValidationError(
                {"parent": "Parent location must belong to the same inventory."}
            )

        ancestor = self.parent
        seen = set()

        while ancestor is not None:
            if self.pk and ancestor.pk == self.pk:
                raise ValidationError(
                    {"parent": "A location hierarchy cannot contain a cycle."}
                )

            if ancestor.pk in seen:
                raise ValidationError(
                    {"parent": "A location hierarchy cannot contain a cycle."}
                )

            seen.add(ancestor.pk)
            ancestor = ancestor.parent

        siblings = Location.objects.filter(
            inventory=self.inventory,
            archived_at__isnull=True,
            name__iexact=self.name,
        ).exclude(pk=self.pk)

        if self.parent_id is None:
            siblings = siblings.filter(parent__isnull=True)
        else:
            siblings = siblings.filter(parent=self.parent)

        if siblings.exists():
            raise ValidationError(
                {"name": "A location with this name already exists here."}
            )

    def __str__(self):
        return self.name

# ITEM

class Item(models.Model):
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    inventory = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        related_name="items",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )

    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    brand = models.CharField(max_length=255, blank=True)
    model_number = models.CharField(max_length=255, blank=True)
    serial_number = models.CharField(max_length=255, blank=True)

    condition = models.CharField(
        max_length=20,
        choices=ItemCondition.choices,
        default=ItemCondition.UNKNOWN,
    )

    quantity = models.PositiveIntegerField(default=1)

    purchase_date = models.DateField(blank=True, null=True)

    purchase_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    # Cached current estimate for fast inventory/dashboard reads.
    # ValuationRun remains the historical source of truth.
    current_estimated_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    manual_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    valuation_date = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name="item_qty_gte_1",
            ),
        ]
        indexes = [
            models.Index(
                fields=["inventory", "archived_at", "-updated_at"],
                name="item_inv_arch_upd_idx",
            ),
        ]

    def clean(self):
        super().clean()
        self.name = self.name.strip()

        # Defense-in-depth. Django save() does not call full_clean()
        # automatically, so DRF serializers/services must enforce these too.
        if self.category_id:
            if self.category.inventory_id != self.inventory_id:
                raise ValidationError(
                    {
                        "category":
                        "Category must belong to the same inventory as the item."
                    }
                )

        if self.location_id:
            if self.location.inventory_id != self.inventory_id:
                raise ValidationError(
                    {
                        "location":
                        "Location must belong to the same inventory as the item."
                    }
                )

    @property
    def effective_value(self):
        if self.manual_value is not None:
            return self.manual_value
        return self.current_estimated_amount

    def __str__(self):
        return self.name

# ATTACHMENT

class Attachment(models.Model):
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="attachments",
    )

    file = models.FileField(
        upload_to="item_attachments/%Y/%m/",
    )

    file_type = models.CharField(
        max_length=20,
        choices=AttachmentType.choices,
        default=AttachmentType.PHOTO,
    )

    # Populate these server-side from the uploaded file.
    original_filename = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveBigIntegerField(blank=True, null=True)

    is_primary = models.BooleanField(default=False)

    uploaded_at = models.DateTimeField(auto_now_add=True)
    archived_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(is_primary=False)
                    | Q(file_type=AttachmentType.PHOTO)
                ),
                name="primary_attachment_is_photo",
            ),
            models.UniqueConstraint(
                fields=["item"],
                condition=Q(
                    is_primary=True,
                    archived_at__isnull=True,
                    file_type=AttachmentType.PHOTO,
                ),
                name="one_active_primary_photo",
            ),
        ]

    def __str__(self):
        return f"{self.get_file_type_display()} - {self.item.name}"

# VALUATION RUN

class ValuationRun(models.Model):
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="valuation_runs",
    )

    # NULL can represent an automated/system-triggered valuation.
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_valuations",
    )

    valuation_type = models.CharField(
        max_length=20,
        choices=ValuationType.choices,
        default=ValuationType.AUTOMATED,
    )

    status = models.CharField(
        max_length=20,
        choices=ValuationStatus.choices,
        default=ValuationStatus.PENDING,
    )

    estimated_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    currency = models.CharField(max_length=3, default="USD")

    range_low = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    range_high = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    # Basis points: 10000 == 100%, 8500 == 85%.
    confidence_bps = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    sample_count = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    algorithm_version = models.CharField(max_length=50, blank=True)

    input_snapshot = models.JSONField(
        default=dict,
        blank=True,
    )

    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(confidence_bps__isnull=True)
                    | Q(
                        confidence_bps__gte=0,
                        confidence_bps__lte=10000,
                    )
                ),
                name="valuation_confidence_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(range_low__isnull=True)
                    | Q(range_high__isnull=True)
                    | Q(range_low__lte=F("range_high"))
                ),
                name="valuation_range_ordered",
            ),
        ]
        indexes = [
            models.Index(
                fields=["item", "-requested_at"],
                name="valuation_item_req_idx",
            ),
            models.Index(
                fields=["status", "requested_at"],
                name="valuation_status_req_idx",
            ),
        ]

    def __str__(self):
        return f"{self.item.name} - {self.get_status_display()}"

# VALUATION SOURCE RESULT

class ValuationSourceResult(models.Model):
    """
    Internal result from one marketplace/provider inside a ValuationRun.
    It keeps the normal Django integer primary key for the MVP.
    """

    valuation_run = models.ForeignKey(
        ValuationRun,
        on_delete=models.CASCADE,
        related_name="source_results",
    )

    source = models.CharField(max_length=100)

    status = models.CharField(
        max_length=20,
        choices=SourceStatus.choices,
        default=SourceStatus.PENDING,
    )

    results_found = models.PositiveIntegerField(default=0)
    results_used = models.PositiveIntegerField(default=0)

    source_estimate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    currency = models.CharField(max_length=3, default="USD")
    error_code = models.CharField(max_length=50, blank=True)

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["valuation_run", "source"],
                name="one_source_per_valuation_run",
            ),
            models.CheckConstraint(
                condition=Q(results_used__lte=F("results_found")),
                name="source_used_lte_found",
            ),
        ]

    def __str__(self):
        return f"{self.source} - {self.valuation_run}"

# COMPARABLE LISTING

class ComparableListing(models.Model):
    """
    Optional persisted marketplace comparable used to explain/debug a valuation.
    """

    source_result = models.ForeignKey(
        ValuationSourceResult,
        on_delete=models.CASCADE,
        related_name="comparable_listings",
    )

    external_listing_id = models.CharField(max_length=255, blank=True)
    url = models.URLField(max_length=2048, blank=True)
    title = models.CharField(max_length=512)

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    shipping = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    currency = models.CharField(max_length=3, default="USD")

    condition_raw = models.CharField(max_length=100, blank=True)
    condition_normalized = models.CharField(max_length=100, blank=True)

    observed_at = models.DateTimeField(blank=True, null=True)

    included_in_estimate = models.BooleanField(default=True)
    exclusion_reason = models.TextField(blank=True)

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
