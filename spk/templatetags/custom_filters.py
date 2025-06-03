# templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """
    Template filter untuk mengakses value dictionary dengan key
    Usage: {{ dictionary|lookup:key }}
    """
    if dictionary and key in dictionary:
        return dictionary[key]
    return 0

@register.filter
def multiply(value, arg):
    """
    Template filter untuk mengalikan dua nilai
    Usage: {{ value|multiply:arg }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def percentage(value):
    """
    Template filter untuk mengubah nilai desimal ke persentase
    Usage: {{ 0.25|percentage }} -> 25%
    """
    try:
        return f"{float(value) * 100:.1f}%"
    except (ValueError, TypeError):
        return "0%"

@register.filter
def get_item(d, key):
    return d.get(key)