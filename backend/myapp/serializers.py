from rest_framework import serializers
from .models import (
    User,
    Inventory,
    Category,
    Location,
    Item,
    Attachment,
    ValuationRun,
    ValuationSourceResult,
    ComparableListing,
)


class UserSerializer(serializers.ModelSerializer):
  class Meta:
    model = User
    fields = [
        "id",
        "public_id",
        "username",
        "email",
        "first_name",
        "last_name",
        "is_active",
        "date_joined",
    ]


class CategorySerializer(serializers.ModelSerializer):

  class Meta:
    model = Category
    fields = "__all__"


class LocationSerializer(serializers.ModelSerializer):
  # Allows the frontend to see sub-locations nested under a parent location
  sub_locations = serializers.PrimaryKeyRelatedField(
      many=True, read_only=True
  )

  class Meta:
    model = Location
    fields = "__all__"


class AttachmentSerializer(serializers.ModelSerializer):

  class Meta:
    model = Attachment
    fields = "__all__"


class ComparableListingSerializer(serializers.ModelSerializer):

  class Meta:
    model = ComparableListing
    fields = "__all__"


class ValuationSourceResultSerializer(serializers.ModelSerializer):
  comparable_listings = ComparableListingSerializer(
      many=True, read_only=True
  )

  class Meta:
    model = ValuationSourceResult
    fields = "__all__"


class ValuationRunSerializer(serializers.ModelSerializer):
  source_results = ValuationSourceResultSerializer(many=True, read_only=True)

  class Meta:
    model = ValuationRun
    fields = "__all__"


class ItemSerializer(serializers.ModelSerializer):
  # Nesting related data so the frontend gets attachments and valuations automatically when fetching an item
  attachments = AttachmentSerializer(many=True, read_only=True)
  valuation_runs = ValuationRunSerializer(many=True, read_only=True)

  class Meta:
    model = Item
    fields = "__all__"


class InventorySerializer(serializers.ModelSerializer):
  categories = CategorySerializer(many=True, read_only=True)
  locations = LocationSerializer(many=True, read_only=True)
  items = ItemSerializer(many=True, read_only=True)

  class Meta:
    model = Inventory
    fields = "__all__"