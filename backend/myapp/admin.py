from django.contrib import admin

# Register your models here.
from .models import (
    Attachment,
    Category,
    ComparableListing,
    Inventory,
    Item,
    Location,
    ValuationRun,
    ValuationSourceResult,
)


admin.site.register(Inventory)
admin.site.register(Category)
admin.site.register(Location)
admin.site.register(Item)
admin.site.register(Attachment)
admin.site.register(ValuationRun)
admin.site.register(ValuationSourceResult)
admin.site.register(ComparableListing)