from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.generic import UpdateView, CreateView

from category.forms import CategoryForm
from stock.models import Stock
from unity.forms import UnityForm
from .form import ProductForm,ProductForm2, VariantFormSet
from .models import Product,Variantes
from django.http import HttpResponseRedirect,HttpResponse
from django.urls import reverse


def product_view(request):
    products=Product.objects.all().order_by('libelle')
    articles = Variantes.objects.all()
    # values('qty','product__pk','product__libelle','product__unity','product__qteEnVente','product__productType','product__stockAlert','product__categorie','product__status','product__manuf_on','product__expiried_on','product__pu','product__created_at')
    form = ProductForm()
    context={
        'Products':articles,
        'page':'product',
        'form':form,
    }
    return render(request,'article/product_list.html',context)


def product_add_view(request):
    form = ProductForm()
    catForm=CategoryForm()
    unitForm=UnityForm()
    context = {
        'form': form,
        'catForm': catForm,
        'unitForm': unitForm,
        'page': 'add_product',
    }
    if request.method == "POST":
        # form = ProductForm(request.POST)
        # if form.is_valid():
        #     form.save()
        #     messages.success(request, " Article Ajouté avec succès")
        #     return redirect('article:article_list_view')
        # messages.error(request, form.errors)
        libelle = request.POST['libelle']
        print("============================================")
        for l in libelle:
            print(l)
        return render(request, 'article/add_product.html', context)
    return render(request, 'article/add_product.html', context)


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


class ProductInline():
    form_class = ProductForm2
    model = Product
    template_name = "add_product.html"

    def form_valid(self, form):
        named_formsets = self.get_named_formsets()
        if not all((x.is_valid() for x in named_formsets.values())):
            return self.render_to_response(self.get_context_data(form=form))

        self.object = form.save()

        # for every formset, attempt to find a specific formset save function
        # otherwise, just save.
        for name, formset in named_formsets.items():
            formset_save_func = getattr(self, 'formset_{0}_valid'.format(name), None)
            if formset_save_func is not None:
                formset_save_func(formset)
            else:
                formset.save()
        return redirect('article:product_list_view')

    def formset_variants_valid(self, formset):
        """
        Hook for custom formset saving.Useful if you have multiple formsets
        """
        variants = formset.save(commit=False)  # self.save_formset(formset, contact)
        # add this 2 lines, if you have can_delete=True parameter
        # set in inlineformset_factory func
        for obj in formset.deleted_objects:
            obj.delete()
        for variant in variants:
            variant.product = self.object
            variant.save()


class ProductCreate(ProductInline, CreateView):

    def get_context_data(self, **kwargs):
        ctx = super(ProductCreate, self).get_context_data(**kwargs)
        ctx['named_formsets'] = self.get_named_formsets()
        return ctx

    def get_named_formsets(self):
        if self.request.method == "GET":
            return {
                'variants': VariantFormSet(prefix='variants'),

            }
        else:
            return {
                'variants': VariantFormSet(self.request.POST or None, self.request.FILES or None, prefix='variants'),

            }


class ProductUpdate(ProductInline, UpdateView):

    def get_context_data(self, **kwargs):
        ctx = super(ProductUpdate, self).get_context_data(**kwargs)
        ctx['named_formsets'] = self.get_named_formsets()
        return ctx

    def get_named_formsets(self):
        return {
            'variants': VariantFormSet(self.request.POST or None, self.request.FILES or None, instance=self.object, prefix='variants'),
        }


def delete_variant(request, pk):
    try:
        variant = Variantes.objects.get(id=pk)
    except Variantes.DoesNotExist:
        messages.success(
            request, 'Object Does not exit'
            )
        return redirect('products:update_product', pk=variant.product.id)

    variant.delete()
    messages.success(
            request, 'Variant deleted successfully'
            )
    return redirect('products:update_product', pk=variant.product.id)


   
    


