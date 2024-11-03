from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect

# Create your views here.
from django.urls import reverse

from . models import UniteVente
from .forms import UnityForm


def unity_view(request):
    unity = UniteVente.objects.all().order_by('unit')
    form = UnityForm()
    context = {
        'unities': unity,
        'page': 'unity',
        'form': form,
    }
    return render(request, 'unity/unity_list.html', context)


def unity_add_view(request):
    unity = UniteVente.objects.all().order_by('unit')
    form = UnityForm()
    context = {
        'form': form,
        'unities': unity,
        'page': 'unity'
    }
    if request.method == "POST":
        form = UnityForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, " L'unité de vente ajoutée avec succès")
            return render(request, 'unity/unity_list.html', context)
        messages.error(request, form.errors)
        return redirect('unity:unity_list_view')
    return render(request, 'unity/unity_list.html', context)


def unity_update_view(request, pk):
    cat = UniteVente.objects.get(pk=pk)
    unity = UniteVente.objects.all().order_by('unit')
    form = UnityForm(request.POST or None, instance=cat)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "modification éffectuée avec succès")
            return redirect('unity:unity_list_view')
        messages.error(request, "Modification échouée verifier les données entrées")
        return redirect('unity:unity_list_view')
    context = {
        'form': form,
    }

    return render(request, 'unity/partial/_unity_modal.html', context)


def unity_delete_view(request, pk):
    unit = UniteVente.objects.get(pk=pk).delete()

    unity = UniteVente.objects.all().order_by('unit')
    context = {
        'unities': unity,
        'page': 'unity'
    }

    return HttpResponseRedirect(reverse('unity:unity_list_view'))

# TODO: ajouter la confirmation avant la modification
