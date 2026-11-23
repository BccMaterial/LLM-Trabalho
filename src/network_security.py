from ipaddress import ip_address
from urllib.parse import urlsplit


def validate_service_base_url(base_url: str, *, setting_name: str) -> str:
    try:
        parsed_url = urlsplit(base_url)
        hostname = parsed_url.hostname
    except ValueError as error:
        raise RuntimeError(f"{setting_name} contém uma URL inválida.") from error

    is_loopback = hostname == "localhost"
    if hostname:
        try:
            is_loopback = is_loopback or ip_address(hostname).is_loopback
        except ValueError:
            pass

    if not hostname or parsed_url.username or parsed_url.password:
        raise RuntimeError(
            f"{setting_name} deve conter um host válido sem credenciais."
        )
    if parsed_url.scheme != "https" and not (
        parsed_url.scheme == "http" and is_loopback
    ):
        raise RuntimeError(
            f"{setting_name} deve usar HTTPS; HTTP só é permitido em loopback."
        )
    return base_url
