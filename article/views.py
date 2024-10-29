from django.http import HttpResponse
from django.shortcuts import redirect, render
from .models import Product

# Create your views here.

def product_list(request):
    context={
        'page':"product",
        'products': Product.objects.all().order_by("Name")
    }
    return render(request,'article/product_list.html',context)


def add_product(request):
    context={
        'page':"add_product",
    }
    return render(request,'article/add_product.html',context)


