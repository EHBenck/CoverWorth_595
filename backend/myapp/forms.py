from django import forms
from django.core.exceptions import ValidationError
from .models import Item, Category, Location

class ItemForm(forms.ModelForm):
    """Form for creating and editing items"""
    
    class Meta:
        model = Item
        fields = [
            'name',
            'category',
            'location',
            'description',
            'brand',
            'model_number',
            'serial_number',
            'condition',
            'quantity',
            'purchase_date',
            'purchase_amount',
            'manual_value',
            'notes',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Item name'}),
            'category': forms.Select(),
            'description': forms.Textarea(attrs={'rows': 3}),
            'brand': forms.TextInput(attrs={'placeholder': 'Brand'}),
            'model_number': forms.TextInput(attrs={'placeholder': 'Model number'}),
            'serial_number': forms.TextInput(attrs={'placeholder': 'Serial number'}),
            'condition': forms.Select(),
            'quantity': forms.NumberInput(attrs={'min': 1}),
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'purchase_amount': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}),
            'manual_value': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, inventory, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.inventory = inventory
        self.instance.inventory = inventory
        
        # Filter categories to only those in this inventory
        self.fields['category'].queryset = Category.objects.filter(
            inventory=inventory,
            archived_at__isnull=True,
        )
        self.fields["location"].queryset = Location.objects.filter(
            inventory=inventory,
            archived_at__isnull=True,
        )
        # Make fields required
        self.fields["name"].required = True
        self.fields["category"].required = True
        self.fields["location"].required = False
        self.fields["purchase_date"].required = True
        self.fields["purchase_amount"].required = True
    
    def clean_location(self):
        location = self.cleaned_data.get("location")

        if location is None:
            return None

        if (location.inventory_id != self.inventory.id or location.archived_at is not None):
            raise ValidationError("Location must belong to the same inventory as the item.")

        return location

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError("Item name is required.")
        return name

    def clean_category(self):
        category = self.cleaned_data.get('category')
        if not category:
            raise ValidationError("Category is required.")
        
        try:
            # Handle whether Django passed a Category object or a raw ID string
            cat_id = category.id if isinstance(category, Category) else int(category)
            
            # Explicitly verify the category belongs to this form's inventory
            category_obj = Category.objects.get(
                id=cat_id, 
                inventory=self.inventory, 
                archived_at__isnull=True
            )
        except (ValueError, Category.DoesNotExist):
            raise ValidationError("Category must belong to the same inventory as the item.")
            
        return category_obj

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity is not None and quantity < 1:
            raise ValidationError("Quantity must be at least 1.")
        return quantity

    def clean(self):
        cleaned_data = super().clean()
        purchase_amount = cleaned_data.get('purchase_amount')
        manual_value = cleaned_data.get('manual_value')
        
        if purchase_amount is not None and purchase_amount < 0:
            raise ValidationError("Purchase amount cannot be negative.")
        
        if manual_value is not None and manual_value < 0:
            raise ValidationError("Manual value cannot be negative.")
            
        # If manual valuation is left blank, default it to the purchase amount
        if not manual_value and purchase_amount is not None:
            cleaned_data['manual_value'] = purchase_amount
            self.instance.manual_value = purchase_amount
        
        return cleaned_data
    
    def save(self, commit=True):
        item = super().save(commit=False)
        item.inventory = self.inventory  # Automatically attach the inventory here
        if commit:
            item.save()
        return item
