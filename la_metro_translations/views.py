import os
from django.conf import settings
from django.shortcuts import render
from django.views.generic import TemplateView


class PromptView(TemplateView):
    template_name = "la_metro_translations/prompt.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        file_path = os.path.join(
            settings.BASE_DIR, "la_metro_translations", "prompt.txt"
        )
        with open(file_path) as f:
            context["prompt_text"] = f.read()
        return context


def robots_txt(request):
    return render(
        request,
        "la_metro_translations/robots.txt",
        {"ALLOW_CRAWL": True if os.getenv("ALLOW_CRAWL") == "True" else False},
        content_type="text/plain",
    )


def page_not_found(request, exception, template_name="404.html"):
    return render(request, template_name, status=404)


def server_error(request, template_name="500.html"):
    return render(request, template_name, status=500)
