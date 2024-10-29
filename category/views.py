
from django.shortcuts import redirect, render
from category.forms import CategoryForm
from category.models import Categorie
from django.http import HttpResponseRedirect,HttpResponse
from django.urls import reverse
from render_block import render_block_to_string
def category_view(request):
    category=Categorie.objects.all().order_by('Name')
    context={
        'Categories':category,
        'page':'category'
    }
    return render(request,'category/category_list.html',context)

def category_rows_view(request):
    category=Categorie.objects.all().order_by('Name')
    context={
        'categories':category,
        'page':'category'
    }
    html=render_block_to_string('category/category_list.html', 'table')
    return HttpResponse(html)

def category_update_view(request,pk):
    cat=Categorie.objects.get(pk=pk)
    categories=Categorie.objects.all().order_by('Name')
    form=CategoryForm(request.POST or None,instance=cat)
    context={
        'form':form,
        'Categories':categories,
        'page':'category'
    }
    if request.method == "POST":
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('category:category_list_view'))  
   
    return render(request,'category/partial/_category_modal.html',context)

def category_delete_view(request,pk):
    cat=Categorie.objects.get(pk=pk).delete()
   
    categories=Categorie.objects.all().order_by('Name')
    context={
        'Categories':categories,
        'page':'category'
    }
    
    return HttpResponseRedirect(reverse('category:category_list_view'))  
   
    