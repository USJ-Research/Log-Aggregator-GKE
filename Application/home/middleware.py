import logging
import re
from django.conf import settings

logger = logging.getLogger('home')

PATH_TAG_PREFIXES = (
    ('/password_reset_confirm/', 'PASSWORDRESETCONFIRM_ACCESSED'),
    ('/password_reset_done/', 'PASSWORDRESETDONE_ACCESSED'),
    ('/password_reset_complete/', 'PASSWORDRESETCOMPLETE_ACCESSED'),
    ('/password_reset/', 'PASSWORDRESET_ACCESSED'),
)

NUMERIC_ID_RE = re.compile(r'/\d+/')
PROFILE_USERNAME_RE = re.compile(r'^/profile/[^/]+/')
PASSWORD_RESET_CONFIRM_RE = re.compile(r'^/password_reset_confirm/[^/]+/[^/]+/')


def normalize_path(path):
    path = NUMERIC_ID_RE.sub('/<id>/', path)
    path = PROFILE_USERNAME_RE.sub('/profile/<username>/', path)
    path = PASSWORD_RESET_CONFIRM_RE.sub('/password_reset_confirm/<uidb64>/<token>/', path)
    return path


class MethodOverrideMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST':
            override = request.POST.get('_method', '').upper()
            if override in ('PUT', 'DELETE'):
                token = request.POST.get('csrfmiddlewaretoken', '')
                if token and not request.META.get(settings.CSRF_HEADER_NAME):
                    request.META[settings.CSRF_HEADER_NAME] = token
                request.method = override
        return self.get_response(request)


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        tag = getattr(request, 'log_tag', None)
        method = request.method
        path = normalize_path(request.path)
        status = response.status_code

        if request.GET.get('next'):
            path = f"{path.rstrip('/')}/redirect"
        elif request.GET:
            path = f"{path.rstrip('/')}/query"

        if not tag and status == 302:
            location = response.get('Location', '')
            if location.startswith('/login'):
                tag = "AUTH_REDIRECT"

        if not tag:
            for prefix, mapped_tag in PATH_TAG_PREFIXES:
                if request.path.startswith(prefix):
                    tag = mapped_tag
                    break

        if not tag and status == 404:
            tag = "NOT_FOUND"
            path = "/<invalid-route>"

        if tag and ':' in tag:
            tag = tag.split(':')[0].strip()

        if not tag:
            return response

        logger.info(f'{tag} "{method} {path}" {status}')

        return response