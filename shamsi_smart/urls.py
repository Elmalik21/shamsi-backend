"""
Shamsi Smart URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse


def custom_404(request, exception):
    return render(request, '404.html', {'page_title': '404 - Not Found'}, status=404)

def custom_500(request):
    return render(request, '500.html', {'page_title': '500 - Server Error'}, status=500)


from django.views.generic import TemplateView

urlpatterns = [
    path('favicon.ico', lambda req: HttpResponse(status=204)),
    path('admin/',      admin.site.urls),
    path('api-docs/',   TemplateView.as_view(template_name='api_docs.html'), name='api-docs'),
    path('',            include(('dashboard.urls', 'dash'), namespace='dash')),
    path('api/v1/',     include('api.urls')),
    path('solar-data/', include('solar_data.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = custom_404
handler500 = custom_500
