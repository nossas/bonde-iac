import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s
import os


class CaddyStack(pulumi.ComponentResource):
    """
    CaddyStack implementa o Caddy como proxy reverso multi-tenant com LoadBalancer automático.
    """

    def __init__(
        self,
        name: str,
        namespace: str,
        k8s_provider,
        environment: str,
        opts=None,
    ):
        super().__init__("custom:caddy:CaddyStack", name, None, opts)

        self.namespace = namespace

        # ✅ LER Caddyfile específico do ambiente
        caddyfile_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "config",
            "caddy",
            f"caddy-{environment}.json",
        )

        try:
            with open(caddyfile_path, "r") as f:
                caddyfile_content = f.read()
            pulumi.log.info(f"✅ Caddyfile carregado: {caddyfile_path}")
        except FileNotFoundError:
            # Fallback básico
            caddyfile_content = """
{}
""".replace(
                "{environment}", environment
            )
            pulumi.log.warn(
                f"⚠️  Caddyfile não encontrado, usando fallback: {caddyfile_path}"
            )

        pulumi.log.info(f"caddy.json: {caddyfile_content}")
        # ConfigMap
        # self.config_map = k8s.core.v1.ConfigMap(
        #     f"{name}-config",
        #     metadata=k8s.meta.v1.ObjectMetaArgs(
        #         name=f"{name}-config", namespace=namespace
        #     ),
        #     data={"Caddyfile": caddyfile_content},
        #     opts=pulumi.ResourceOptions(provider=k8s_provider, parent=self),
        # )
        self.config_map = k8s.core.v1.ConfigMap(
            f"{name}-config",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=f"{name}-config", namespace=namespace
            ),
            data={
                "Caddyfile": "",  # Pode manter vazio ou remover
                "caddy.json": caddyfile_content,
            },
            opts=pulumi.ResourceOptions(provider=k8s_provider, parent=self),
        )

        # Deployment
        self.deployment = k8s.apps.v1.Deployment(
            f"{name}-deployment",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=name,
                namespace=namespace,
                labels={"app": "caddy", "component": "ingress"},
            ),
            spec=k8s.apps.v1.DeploymentSpecArgs(
                replicas=1,
                selector=k8s.meta.v1.LabelSelectorArgs(match_labels={"app": "caddy"}),
                template=k8s.core.v1.PodTemplateSpecArgs(
                    metadata=k8s.meta.v1.ObjectMetaArgs(
                        labels={"app": "caddy"},
                        # ✅ Annotation para rolling update quando ConfigMap mudar
                        annotations={"config/revision": "1"},
                    ),
                    spec=k8s.core.v1.PodSpecArgs(
                        containers=[
                            k8s.core.v1.ContainerArgs(
                                name="caddy",
                                image="caddy:2-alpine",
                                args=[
                                    "caddy",
                                    "run",
                                    "--config",
                                    "/etc/caddy/caddy.json",  # ✅ Aponta para o JSON
                                ],
                                ports=[
                                    k8s.core.v1.ContainerPortArgs(
                                        container_port=80, name="http"
                                    ),
                                    k8s.core.v1.ContainerPortArgs(
                                        container_port=443, name="https"
                                    ),
                                ],
                                volume_mounts=[
                                    k8s.core.v1.VolumeMountArgs(
                                        name="caddy-config", mount_path="/etc/caddy"
                                    ),
                                    k8s.core.v1.VolumeMountArgs(
                                        name="caddy-data", mount_path="/data"
                                    ),
                                ],
                                resources=k8s.core.v1.ResourceRequirementsArgs(
                                    requests={"memory": "64Mi", "cpu": "50m"},
                                    limits={"memory": "128Mi", "cpu": "100m"},
                                ),
                            )
                        ],
                        volumes=[
                            k8s.core.v1.VolumeArgs(
                                name="caddy-config",
                                config_map=k8s.core.v1.ConfigMapVolumeSourceArgs(
                                    name=self.config_map.metadata["name"]
                                ),
                            ),
                            k8s.core.v1.VolumeArgs(
                                name="caddy-data",
                                empty_dir=k8s.core.v1.EmptyDirVolumeSourceArgs(),
                            ),
                        ],
                    ),
                ),
            ),
            opts=pulumi.ResourceOptions(
                provider=k8s_provider, parent=self, depends_on=[self.config_map]
            ),
        )

        # ✅ SERVICE COM LOADBALANCER AUTOMÁTICO
        self.service = k8s.core.v1.Service(
            f"{name}-service",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=name,
                namespace=namespace,
                labels={"app": "caddy", "environment": environment},
                annotations={
                    "service.beta.kubernetes.io/aws-load-balancer-type": "nlb",  # ou "elb"
                    "service.beta.kubernetes.io/aws-load-balancer-scheme": "internet-facing",
                    "service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled": "true",
                },
            ),
            spec=k8s.core.v1.ServiceSpecArgs(
                type="LoadBalancer",  # ✅ LOADBALANCER AUTOMÁTICO
                external_traffic_policy="Local",
                selector={"app": "caddy"},
                ports=[
                    k8s.core.v1.ServicePortArgs(
                        port=80, target_port=80, protocol="TCP", name="http"
                    ),
                    k8s.core.v1.ServicePortArgs(
                        port=443, target_port=443, protocol="TCP", name="https"
                    ),
                ],
            ),
            opts=pulumi.ResourceOptions(
                provider=k8s_provider,
                parent=self,
                depends_on=[self.deployment],  # ✅ Garantir que o deployment existe
            ),
        )

        # ✅ URL do Load Balancer para export
        self.load_balancer_url = self.service.status.apply(
            lambda status: (
                f"http://{status.load_balancer.ingress[0].hostname}"
                if status and status.load_balancer and status.load_balancer.ingress
                else "⏳ Load Balancer provisionando..."
            )
        )


def create_caddy(name: str, namespace: str, k8s_provider, environment: str):
    """
    Cria o Caddy para um ambiente específico com LoadBalancer automático.

    Args:
        name: Nome do componente
        namespace: Namespace Kubernetes
        k8s_provider: Provider Kubernetes
        environment: 'sandbox' ou 'production'
    """
    return CaddyStack(name, namespace, k8s_provider, environment)
