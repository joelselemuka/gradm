from .models import Product

# Create your views here.

# BLOCK UNITY

from django.shortcuts import render


# END BLOCK UNITY




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


