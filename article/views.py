from django.contrib import messages
from django.shortcuts import redirect, render

from stock.models import Stock
from .form import ProductForm
from .models import Product
from django.http import HttpResponseRedirect,HttpResponse
from django.urls import reverse


def product_view(request):
    products=Product.objects.all().order_by('libelle')
    articles = Stock.objects.all().values('qty','product__pk','product__libelle','product__unity','product__qteEnVente','product__productType','product__stockAlert','product__categorie','product__status')
    form = ProductForm()
    context={
        'Products':articles,
        'page':'product',
        'form':form,
    }
    return render(request,'article/product_list.html',context)


def product_add_view(request):
    products = Product.objects.all().order_by('libelle')
    form = ProductForm()
    context = {
        'form': form,
        'products': products,
        'page': 'add_product'
    }
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, " Article Ajouté avec succès")
            return redirect('article:article_list_view')
        messages.error(request, form.errors)
        return redirect('article:article_list_view')
    return render(request, 'article/article_list.html', context)


def Product_update_view(request, pk):
    cat=Product.objects.get(pk=pk)
    Products=Product.objects.all().order_by('libelle')
    form = ProductForm(request.POST or None, instance=cat)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request,"modification éffectuée avec succès")
            return redirect('Product:Product_list_view')
        messages.error(request, "Modification échouée verifier les données entrées")
        return redirect('Product:Product_list_view')
    context = {
        'form': form,
    }

    return render(request,'article/add_product.html',context)



def Product_delete_view(request,pk):
    cat=Product.objects.get(pk=pk).delete()
   
    Products=Product.objects.all().order_by('libelle')
    context={
        'products':Products,
        'page':'Product'
    }
    
    return HttpResponseRedirect(reverse('Product:Product_list_view'))  
   
    


