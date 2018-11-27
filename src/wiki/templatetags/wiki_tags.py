import re
import jieba

from django import template
from django.apps import apps
from django.conf import settings as django_settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Model
from django.forms import BaseForm
from django.template.defaultfilters import striptags
from django.utils.http import urlquote
from django.utils.safestring import mark_safe
from wiki import models
from wiki.conf import settings
from wiki.core.plugins import registry as plugin_registry

register = template.Library()


# Cache for looking up objects for articles... article_for_object is
# called more than once per page in multiple template blocks.
_cache = {}


@register.simple_tag(takes_context=True)
def article_for_object(context, obj):
    if not isinstance(obj, Model):
        raise TypeError(
            "A Wiki article can only be associated to a Django Model "
            "instance, not %s" % type(obj)
        )

    content_type = ContentType.objects.get_for_model(obj)

    # TODO: This is disabled for now, as it should only fire once per request
    # Maybe store cache in the request object?
    if True or obj not in _cache:
        try:
            article = models.ArticleForObject.objects.get(
                content_type=content_type,
                object_id=obj.pk).article
        except models.ArticleForObject.DoesNotExist:
            article = None
        _cache[obj] = article
    return _cache[obj]


@register.inclusion_tag('wiki/includes/render.html', takes_context=True)
def wiki_render(context, article, preview_content=None):

    if preview_content:
        content = article.render(preview_content=preview_content)
    elif article.current_revision:
        content = article.get_cached_content(user=context.get('user'))
    else:
        content = None

    context.update({
        'article': article,
        'content': content,
        'preview': preview_content is not None,
        'plugins': plugin_registry.get_plugins(),
        'STATIC_URL': django_settings.STATIC_URL,
        'CACHE_TIMEOUT': settings.CACHE_TIMEOUT,
    })
    return context


@register.inclusion_tag('wiki/includes/form.html', takes_context=True)
def wiki_form(context, form_obj):
    if not isinstance(form_obj, BaseForm):
        raise TypeError(
            "Error including form, it's not a form, it's a %s" %
            type(form_obj))
    context.update({'form': form_obj})
    return context


@register.inclusion_tag('wiki/includes/messages.html', takes_context=True)
def wiki_messages(context):

    messages = context.get('messages', [])
    for message in messages:
        message.css_class = settings.MESSAGE_TAG_CSS_CLASS[message.level]
    context.update({
        'messages': messages
    })
    return context


# XXX html strong tag is hardcoded
@register.filter
def get_content_snippet(content, query, max_words=60):
    """
    截取和高亮
    """
    content = striptags(content)
    for keyword in jieba.cut(query):
        content = content.replace(keyword, '<span style="background-color:aqua" class="search-highlight">{}</span>'.format(keyword))
    return mark_safe(content)


@register.filter
def can_read(obj, user):
    """
    Takes article or related to article model.
    Check if user can read article.
    """
    return obj.can_read(user)


@register.filter
def can_write(obj, user):
    """
    Takes article or related to article model.
    Check if user can write article.
    """
    return obj.can_write(user)


@register.filter
def can_delete(obj, user):
    """
    Takes article or related to article model.
    Check if user can delete article.
    """
    return obj.can_delete(user)


@register.filter
def can_moderate(obj, user):
    """
    Takes article or related to article model.
    Check if user can moderate article.
    """
    return obj.can_moderate(user)


@register.filter
def is_locked(model):
    """
    Check if article is locked.
    """
    return model.current_revision and model.current_revision.locked


@register.simple_tag(takes_context=True)
def login_url(context):
    request = context['request']
    qs = request.META.get('QUERY_STRING', '')
    if qs:
        qs = urlquote('?' + qs)
    else:
        qs = ''
    return settings.LOGIN_URL + "?next=" + request.path + qs


@register.filter
def plugin_enabled(plugin_name):
    """
    Example: {% if 'wiki.plugins.notifications'|plugin_enabled %}

    :param: plugin_name: String specifying the full name of the plugin, e.g.
                         'wiki.plugins.attachments'
    """
    return apps.is_installed(plugin_name)


@register.filter
def wiki_settings(name):
    return getattr(settings, name, "")


@register.filter
def starts_with(value, arg):
    return value.startswith(arg)
