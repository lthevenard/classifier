"""Configuracoes compartilhadas do projeto."""

from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_EMAIL_ENV = "INLABS_EMAIL"
DEFAULT_PASSWORD_ENV = "INLABS_PASSWORD"


class MissingCredentialsError(RuntimeError):
    """Erro levantado quando as credenciais do INLABS nao estao no ambiente."""


@dataclass(frozen=True)
class InlabsCredentials:
    email: str
    password: str


def read_inlabs_credentials(
    email_env: str = DEFAULT_EMAIL_ENV,
    password_env: str = DEFAULT_PASSWORD_ENV,
) -> InlabsCredentials:
    """Le credenciais do INLABS a partir de variaveis de ambiente."""

    email = os.getenv(email_env)
    password = os.getenv(password_env)

    missing = [
        env_name
        for env_name, value in ((email_env, email), (password_env, password))
        if not value
    ]
    if missing:
        missing_list = ", ".join(missing)
        raise MissingCredentialsError(
            f"Credenciais ausentes. Defina as variaveis de ambiente: {missing_list}."
        )

    return InlabsCredentials(email=email or "", password=password or "")
