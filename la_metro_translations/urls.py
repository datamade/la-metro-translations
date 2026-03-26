from django.conf import settings
from django.urls import include, path
from django.contrib import admin

from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls

from la_metro_translations import views
from la_metro_translations.api import views as api_views

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("documents/", include(wagtaildocs_urls)),
    path(
        "api/update-documents/",
        api_views.DocumentUpdateView.as_view(),
        name="update_documents",
    ),
    path("robots.txt/", views.robots_txt),
    path("pages/", include(wagtail_urls)),
    path("", include(wagtailadmin_urls)),
]

handler404 = "la_metro_translations.views.page_not_found"
handler500 = "la_metro_translations.views.server_error"


if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    # Serve static and media files from development server
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
