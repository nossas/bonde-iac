import pulumi
import pulumi_kubernetes as k8s


class OnDemandService(pulumi.ComponentResource):
    """
    Serviço on-demand básico que sempre responde 200 para qualquer domínio
    """

    def __init__(
        self,
        name: str,
        namespace: str,
        k8s_provider,
        environment: str,
        opts=None,
    ):
        super().__init__("custom:app:OnDemandService", name, None, opts)

        self.namespace = namespace

        # Deployment do serviço on-demand
        self.deployment = k8s.apps.v1.Deployment(
            f"{name}-deployment",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=name,
                namespace=namespace,
                labels={"app": "on-demand", "component": "backend"},
            ),
            spec=k8s.apps.v1.DeploymentSpecArgs(
                replicas=1,
                selector=k8s.meta.v1.LabelSelectorArgs(
                    match_labels={"app": "on-demand"}
                ),
                template=k8s.core.v1.PodTemplateSpecArgs(
                    metadata=k8s.meta.v1.ObjectMetaArgs(
                        labels={"app": "on-demand"},
                    ),
                    spec=k8s.core.v1.PodSpecArgs(
                        containers=[
                            k8s.core.v1.ContainerArgs(
                                name="on-demand",
                                image="nossas/tls-on-demand:latest",
                                ports=[
                                    k8s.core.v1.ContainerPortArgs(
                                        container_port=3005, name="http"
                                    )
                                ],
                                env=[
                                    k8s.core.v1.EnvVarArgs(
                                        name="DATABASE_URL",
                                        value_from=k8s.core.v1.EnvVarSourceArgs(
                                            secret_key_ref=k8s.core.v1.SecretKeySelectorArgs(
                                                name="bonde-database-url",
                                                key="BONDE_DATABASE_URL",
                                            )
                                        ),
                                    ),
                                    k8s.core.v1.EnvVarArgs(
                                        name="ENVIRONMENT", value=environment
                                    ),
                                    # ✅ Adicione outras variáveis que sua app precisa
                                    # k8s.core.v1.EnvVarArgs(
                                    #     name="ALLOWED_DOMAINS",
                                    #     value="bonde.org,meurio.org.br,nossas.org",
                                    # ),
                                ],
                                resources=k8s.core.v1.ResourceRequirementsArgs(
                                    requests={"memory": "64Mi", "cpu": "50m"},
                                    limits={"memory": "128Mi", "cpu": "100m"},
                                ),
                                # Probes para healthz da aplicação
                                liveness_probe=k8s.core.v1.ProbeArgs(
                                    http_get=k8s.core.v1.HTTPGetActionArgs(
                                        path="/healthz",
                                        port=3005,
                                    ),
                                    initial_delay_seconds=15,
                                    period_seconds=20,
                                ),
                                readiness_probe=k8s.core.v1.ProbeArgs(
                                    http_get=k8s.core.v1.HTTPGetActionArgs(
                                        path="/healthz", port=3005
                                    ),
                                    initial_delay_seconds=5,
                                    period_seconds=10,
                                ),
                            )
                        ],
                    ),
                ),
            ),
            opts=pulumi.ResourceOptions(provider=k8s_provider, parent=self),
        )

        # Service para o on-demand
        self.service = k8s.core.v1.Service(
            f"{name}-service",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=name,
                namespace=namespace,
                labels={"app": "on-demand", "environment": environment},
            ),
            spec=k8s.core.v1.ServiceSpecArgs(
                type="ClusterIP",
                selector={"app": "on-demand"},
                ports=[
                    k8s.core.v1.ServicePortArgs(
                        port=80, target_port=3005, protocol="TCP", name="http"
                    ),
                ],
            ),
            opts=pulumi.ResourceOptions(
                provider=k8s_provider,
                parent=self,
                depends_on=[self.deployment],
            ),
        )

        # URL do serviço (interno)
        self.service_url = f"http://{name}.{namespace}.svc.cluster.local"


def create_on_demand_service(name: str, namespace: str, k8s_provider, environment: str):
    """
    Cria o serviço on-demand básico
    """
    return OnDemandService(name, namespace, k8s_provider, environment)
