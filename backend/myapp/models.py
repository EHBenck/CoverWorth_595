import uuid
from django.db import models


class User(models.Model):
  public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
  username = models.CharField(max_length=150, unique=True)
  email = models.EmailField(unique=True)
  password = models.CharField(max_length=128)
  first_name = models.CharField(max_length=150, blank=True)
  last_name = models.CharField(max_length=150, blank=True)
  is_active = models.BooleanField(default=True)
  date_joined = models.DateTimeField(auto_now_add=True)

  def __str__(self):
    return self.username


class Inventory(models.Model):
  public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
  owner = models.ForeignKey(
      User, on_delete=models.CASCADE, related_name="inventories"
  )
  name = models.CharField(max_length=255)
  description = models.TextField(blank=True, null=True)
  default_currency = models.CharField(max_length=3)
  inventory_type = models.CharField(max_length=100)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)
  archived_at = models.DateTimeField(blank=True, null=True)

  def __str__(self):
    return self.name


class Category(models.Model):
  public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
  inventory = models.ForeignKey(
      Inventory, on_delete=models.CASCADE, related_name="categories"
  )
  name = models.CharField(max_length=255)
  description = models.TextField(blank=True, null=True)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)
  archived_at = models.DateTimeField(blank=True, null=True)

  def __str__(self):
    return self.name


class Location(models.Model):
  public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
  inventory = models.ForeignKey(
      Inventory, on_delete=models.CASCADE, related_name="locations"
  )
  parent = models.ForeignKey(
      "self",
      on_delete=models.CASCADE,
      null=True,
      blank=True,
      related_name="sub_locations",
  )
  name = models.CharField(max_length=255)
  description = models.TextField(blank=True, null=True)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)
  archived_at = models.DateTimeField(blank=True, null=True)

  def __str__(self):
    return self.name


class Item(models.Model):
  public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
  inventory = models.ForeignKey(
      Inventory, on_delete=models.CASCADE, related_name="items"
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
  description = models.TextField(blank=True, null=True)
  brand = models.CharField(max_length=255, blank=True, null=True)
  model_number = models.CharField(max_length=255, blank=True, null=True)
  serial_number = models.CharField(max_length=255, blank=True, null=True)
  condition = models.CharField(max_length=100, blank=True, null=True)
  quantity = models.IntegerField(default=1)
  purchase_date = models.DateField(blank=True, null=True)
  purchase_currency = models.CharField(max_length=3, blank=True, null=True)
  current_estimated_amount = models.CharField(
      max_length=50, blank=True, null=True
  )
  current_estimate_currency = models.CharField(
      max_length=3, blank=True, null=True
  )
  manual_value = models.IntegerField(blank=True, null=True)
  manual_value_currency = models.CharField(max_length=3, blank=True, null=True)
  valuation_date = models.DateTimeField(blank=True, null=True)
  notes = models.TextField(blank=True, null=True)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)
  archived_at = models.DateTimeField(blank=True, null=True)

  def __str__(self):
    return self.name


class Attachment(models.Model):
  public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
  item = models.ForeignKey(
      Item, on_delete=models.CASCADE, related_name="attachments"
  )
  file_path = models.CharField(max_length=512)
  file_type = models.CharField(max_length=100)
  mime_type = models.CharField(max_length=100)
  file_size = models.IntegerField()
  is_primary = models.BooleanField(default=False)
  uploaded_at = models.DateTimeField(auto_now_add=True)
  archived_at = models.DateTimeField(blank=True, null=True)


class ValuationRun(models.Model):
  public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
  item = models.ForeignKey(
      Item, on_delete=models.CASCADE, related_name="valuation_runs"
  )
  valuation_type = models.CharField(max_length=100)
  status = models.CharField(max_length=50)
  estimated_amount = models.IntegerField(blank=True, null=True)
  currency = models.CharField(max_length=3, blank=True, null=True)
  range_low = models.IntegerField(blank=True, null=True)
  range_high = models.IntegerField(blank=True, null=True)
  confidence_bps = models.IntegerField(blank=True, null=True)
  sample_count = models.IntegerField(blank=True, null=True)
  algorithm_version = models.CharField(max_length=50, blank=True, null=True)
  input_snapshot = models.TextField(blank=True, null=True)
  error_code = models.CharField(max_length=50, blank=True, null=True)
  error_message = models.TextField(blank=True, null=True)
  requested_at = models.DateTimeField(blank=True, null=True)
  completed_at = models.DateTimeField(blank=True, null=True)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)
  archived_at = models.DateTimeField(blank=True, null=True)


class ValuationSourceResult(models.Model):
  public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
  valuation_run = models.ForeignKey(
      ValuationRun, on_delete=models.CASCADE, related_name="source_results"
  )
  source = models.CharField(max_length=100)
  status = models.CharField(max_length=50)
  results_found = models.IntegerField(default=0)
  source_estimate = models.IntegerField(blank=True, null=True)
  currency = models.CharField(max_length=3, blank=True, null=True)
  error_code = models.CharField(max_length=50, blank=True, null=True)
  metadata = models.TextField(blank=True, null=True)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)


class ComparableListing(models.Model):
  public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
  source_result = models.ForeignKey(
      ValuationSourceResult,
      on_delete=models.CASCADE,
      related_name="comparable_listings",
  )
  external_listing_id = models.CharField(max_length=255, blank=True, null=True)
  url = models.URLField(max_length=1024)
  title = models.CharField(max_length=512)
  price = models.IntegerField(blank=True, null=True)
  shipping = models.IntegerField(blank=True, null=True)
  currency = models.CharField(max_length=3, blank=True, null=True)
  condition_raw = models.CharField(max_length=100, blank=True, null=True)
  condition_normalized = models.CharField(max_length=100, blank=True, null=True)
  observed_at = models.DateTimeField(blank=True, null=True)
  included_in_estimate = models.BooleanField(default=True)
  exclusion_reason = models.TextField(blank=True, null=True)
  metadata = models.TextField(blank=True, null=True)
  created_at = models.DateTimeField(auto_now_add=True)