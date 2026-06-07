"""Модуль для работы с доменами - теперь использует helpers."""
from .helpers import extract_domain, is_excluded_domain, load_excluded_domains

__all__ = ['extract_domain', 'is_excluded_domain', 'load_excluded_domains']
