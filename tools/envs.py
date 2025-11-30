import base64
import json
import pulumi
import pulumi_kubernetes as k8s
from urllib.parse import urlparse
from typing import Dict


def load_env_secrets(
    namespace: k8s.core.v1.Namespace, provider: k8s.Provider
) -> Dict[str, k8s.core.v1.Secret]:
    # Criar secrets
    config = pulumi.Config("apps")

    bonde_database_url = k8s.core.v1.Secret(
        "bonde-database-url",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="bonde-database-url",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "DATABASE_URL": config.require_secret("bonde-database-url"),
            "BONDE_DATABASE_URL": config.require_secret("bonde-database-url"),
            "HASURA_GRAPHQL_DATABASE_URL": config.require_secret("bonde-database-url"),
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    votepeloclima_database_url = k8s.core.v1.Secret(
        "votepeloclima-database-url",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="votepeloclima-database-url",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "HASURA_GRAPHQL_VOTEPELOCLIMA_DATABASE_URL": config.require_secret(
                "votepeloclima-database-url"
            ),
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # ✅ N8N Database Secret com parsing da URL
    n8n_database_url = config.require_secret("n8n-database-url")

    n8n_database_secret = k8s.core.v1.Secret(
        "n8n-database-secret",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="n8n-database-secret",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "DB_POSTGRESDB_DATABASE": n8n_database_url.apply(
                lambda url: (
                    urlparse(url).path.replace("/", "") if urlparse(url).path else "n8n"
                )
            ),
            "DB_POSTGRESDB_HOST": n8n_database_url.apply(
                lambda url: urlparse(url).hostname
            ),
            "DB_POSTGRESDB_PASSWORD": n8n_database_url.apply(
                lambda url: urlparse(url).password or ""
            ),
            "DB_POSTGRESDB_PORT": n8n_database_url.apply(
                lambda url: str(urlparse(url).port) if urlparse(url).port else "5432"
            ),
            "DB_POSTGRESDB_USER": n8n_database_url.apply(
                lambda url: urlparse(url).username or "n8n_user"
            ),
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )

    n8n_smtp_url = config.require_secret("n8n-smtp-url")
    
    smtp_secret = k8s.core.v1.Secret(
        "smtp-secret",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="smtp-secret",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "N8N_SMTP_HOST": n8n_smtp_url.apply(
                lambda url: urlparse(url).hostname
            ),
            "SMTP_HOST": n8n_smtp_url.apply(
                lambda url: urlparse(url).hostname
            ),
            "N8N_SMTP_PORT": n8n_smtp_url.apply(
                lambda url: str(urlparse(url).port) if urlparse(url).port else "587"
            ),
            "SMTP_PORT": n8n_smtp_url.apply(
                lambda url: str(urlparse(url).port) if urlparse(url).port else "587"
            ),
            "N8N_SMTP_USER": n8n_smtp_url.apply(
                lambda url: urlparse(url).username or "user"
            ),
            "SMTP_USERNAME": n8n_smtp_url.apply(
                lambda url: urlparse(url).username or "user"
            ),
            "N8N_SMTP_PASS": n8n_smtp_url.apply(
                lambda url: urlparse(url).password or "pass"
            ),
            "SMTP_PASSWORD": n8n_smtp_url.apply(
                lambda url: urlparse(url).password or "pass"
            ),
        },
    )
    
    n8n_webhook_secret = k8s.core.v1.Secret(
        "n8n-webhook-secret",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="n8n-webhook-secret",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "N8N_WEBHOOK_SECRET": config.require_secret("n8n-webhook-secret"),
            "N8N_WEBHOOK_TRIGGER_POSTGRES_AUTH": config.require_secret("n8n-webhook-secret"),
        }
    )

    action_secret = k8s.core.v1.Secret(
        "action-secret",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="action-secret",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "ACTION_SECRET_KEY": config.require_secret("action-secret"),
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    hasura_admin_secret = k8s.core.v1.Secret(
        "hasura-admin-secret",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="hasura-admin-secret",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            # TODO: Remover variável REACT_APP_API_GRAPHQL_SECRET.
            "REACT_APP_API_GRAPHQL_SECRET": config.require_secret("hasura-admin-secret"),
            # TODO: Verificar uso da variável HASURA_SECRET nas apis.
            "HASURA_SECRET": config.require_secret("hasura-admin-secret"),
            "HASURA_GRAPHQL_ADMIN_SECRET": config.require_secret("hasura-admin-secret"),
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    pagarme_secret = k8s.core.v1.Secret(
        "pagarme-key",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="pagarme-key",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "PAGARME_API_KEY": config.require_secret("pagarme-key"),
            "REACT_APP_PAGARME_KEY": config.require_secret("pagarme-key"),
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    aws_access_key = k8s.core.v1.Secret(
        "aws-access-key",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="aws-access-key",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "AWS_ACCESS_KEY": config.require_secret("aws-access-key"),
            "AWS_ID": config.require_secret("aws-access-key")
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    aws_secret_key = k8s.core.v1.Secret(
        "aws-secret-key",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="aws-secret-key",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "AWS_SECRET_KEY": config.require_secret("aws-secret-key"),
            "AWS_SECRET": config.require_secret("aws-secret-key"),
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    jwt_secret = k8s.core.v1.Secret(
        "jwt-secret",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="jwt-secret",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "JWT_SECRET": config.require_secret("jwt-secret"),
            "HASURA_GRAPHQL_JWT_SECRET": pulumi.Output.secret(
                config.require_secret("jwt-secret").apply(
                    lambda key: json.dumps(
                        {
                            "type": "HS256",
                            "key": key,
                            "claims_format": "json",
                            "header": {"type": "Cookie", "name": "session"},
                        }
                    )
                )
            ),
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    elasticsearch_cloud_id = k8s.core.v1.Secret(
        "elasticsearch-cloud-id",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="elasticsearch-cloud-id",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "ELASTICSEARCH_CLOUD_ID": config.require_secret("elasticsearch-cloud-id"),
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    elasticsearch_password = k8s.core.v1.Secret(
        "elasticsearch-password",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="elasticsearch-password",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "ELASTICSEARCH_PASSWORD": config.require_secret("elasticsearch-password"),
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    elastic_apm_secret_token = k8s.core.v1.Secret(
        "elastic-apm-secret-token",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="elastic-apm-secret-token",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "ELASTIC_APM_SECRET_TOKEN": config.require_secret(
                "elastic-apm-secret-token"
            ),
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    elastic_apm_server_url = k8s.core.v1.Secret(
        "elastic-apm-server-url",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="elastic-apm-server-url",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "ELASTIC_APM_SERVER_URL": config.require_secret("elastic-apm-server-url"),
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    sendgrid_api_key = k8s.core.v1.Secret(
        "sendgrid-api-key",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="sendgrid-api-key",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "SENDGRID_API_KEY": config.require_secret("sendgrid-api-key"),
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    sendgrid_webhook_key = k8s.core.v1.Secret(
        "sendgrid-webhook-key",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="sendgrid-webhook-key",
            namespace=namespace.metadata["name"],
        ),
        string_data={
            "SENDGRID_WEBHOOK_KEY": config.require_secret("sendgrid-webhook-key"),
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )
    
    ghcr_auth = k8s.core.v1.Secret(
        "ghcr-auth",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="ghcr-auth",
            namespace=namespace.metadata["name"],
        ),
        type="kubernetes.io/dockerconfigjson",
        string_data={
            ".dockerconfigjson": config.require_secret("ghcr-auth").apply(
                lambda auth: pulumi.Output.json_dumps({
                    "auths": {
                        "ghcr.io": {
                            "auth": base64.b64encode(auth.encode()).decode()
                        }
                    }
                })
            )
        }
    )

    return dict(
        bonde_database_url=bonde_database_url,
        votepeloclima_database_url=votepeloclima_database_url,
        n8n_database_secret=n8n_database_secret,
        smtp_secret=smtp_secret,
        n8n_webhook_secret=n8n_webhook_secret,
        action_secret=action_secret,
        hasura_admin_secret=hasura_admin_secret,
        pagarme_secret=pagarme_secret,
        aws_access_key=aws_access_key,
        aws_secret_key=aws_secret_key,
        jwt_secret=jwt_secret,
        elasticsearch_cloud_id=elasticsearch_cloud_id,
        elasticsearch_password=elasticsearch_password,
        elastic_apm_secret_token=elastic_apm_secret_token,
        elastic_apm_server_url=elastic_apm_server_url,
        sendgrid_api_key=sendgrid_api_key,
        sendgrid_webhook_key=sendgrid_webhook_key,
        ghcr_auth=ghcr_auth
    )
