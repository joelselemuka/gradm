from django.core.validators import MinValueValidator
from django.db import models
from apps.products.models import Category, ProductVariant
class Promotion(models.Model):
    class Type(models.TextChoices): PERCENT="PERCENT","Pourcentage"; FIXED="FIXED","Montant fixe"
    name=models.CharField(max_length=150)
    promotion_type=models.CharField(max_length=10,choices=Type.choices)
    value=models.DecimalField(max_digits=14,decimal_places=2,validators=[MinValueValidator(0)])
    variant=models.ForeignKey(ProductVariant,null=True,blank=True,on_delete=models.PROTECT,related_name="promotions")
    category=models.ForeignKey(Category,null=True,blank=True,on_delete=models.PROTECT,related_name="promotions")
    min_quantity=models.PositiveIntegerField(default=1)
    priority=models.PositiveIntegerField(default=0)
    starts_at=models.DateTimeField()
    ends_at=models.DateTimeField()
    active=models.BooleanField(default=True)
    class Meta: indexes=[models.Index(fields=["active","starts_at","ends_at","priority"])]
