"""
URL configuration for coverworth_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import path
from myapp.models import Item
from myapp import views

def health_check(request):
    """Verify Django and the database are connected."""

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        item_count = Item.objects.count()

    except Exception as e:
        return JsonResponse(
            {
                "status": "error",
                "database": "disconnected",
                "message": "CoverWorth backend cannot reach the database",
                "detail": str(e),
            },
            status=503,
        )

    return JsonResponse(
        {
            "status": "ok",
            "database": "connected",
            "message": "CoverWorth backend, schema, and database are connected",
            "item_rows": item_count,
        }
    )


def home(request):
    return JsonResponse(
        {
            "message": "CoverWorth backend is running",
            "health": "/api/health/",
            "dashboard": "/api/dashboard/",
            "items": "/api/items/",
        }
    )


urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health-check"),
    path("api/dashboard/", views.dashboard_summary, name="dashboard-summary"),
    path("api/items/", views.item_list, name="item-list"),
]