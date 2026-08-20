from django.contrib import admin
from .models import Brand, Category, Product, ProductVariant

admin.site.register([Brand, Category, Product, ProductVariant])
