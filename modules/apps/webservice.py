from typing import Dict, List, Optional, Any, Union, List
from pydantic import BaseModel
import pulumi
import pulumi_kubernetes as k8s


class ContainerConfig(BaseModel):
    image: str
    image_pull_secrets: Optional[List[str]] = None
    image_pull_policy: Optional[str] = None
    port: int
    command: Optional[List[str]] = None
    args: Optional[List[str]] = None
    env: Dict[str, str] = {}
    env_from_secret: Dict[str, str] = {}  # { ENV_VAR: secret_name }
    resources: Dict[str, Any] = {
        "requests": {"memory": "64Mi", "cpu": "50m"},
        "limits": {"memory": "128Mi", "cpu": "100m"},
    }
    liveness_probe_path: Optional[str] = "/health"
    readiness_probe_path: Optional[str] = "/ready"
    startup_probe_path: Optional[str] = None


class ServiceConfig(BaseModel):
    type: str = "ClusterIP"  # ClusterIP, NodePort, LoadBalancer
    port: int = 80
    target_port: Optional[int] = None
    annotations: Dict[str, str] = {}


class IngressConfig(BaseModel):
    enabled: bool = False
    host: Optional[str] = None
    path: str = "/"
    tls_secret: Optional[str] = None
    annotations: Dict[str, str] = {}


class WebServiceConfig(BaseModel):
    name: str
    namespace: str
    replicas: int = 1
    container: ContainerConfig
    service: ServiceConfig = ServiceConfig()
    ingress: IngressConfig = IngressConfig()
    labels: Dict[str, str] = {}
    annotations: Dict[str, str] = {}
    volumes: List[Dict[str, Any]] = []
    service_account: Optional[str] = None


class WebService(pulumi.ComponentResource):
    def __init__(
        self,
        name: str,
        config: WebServiceConfig,
        opts: Optional[pulumi.ResourceOptions] = None,
    ):
        super().__init__("custom:apps:WebService", name, {}, opts)

        self.config = config
        self.deployment = self._create_deployment()
        self.service = self._create_service() if config.service else None
        self.ingress = self._create_ingress() if config.ingress.enabled else None

        self.register_outputs(
            {
                "deployment_name": self.deployment.metadata.name,
                "service_name": self.service.metadata.name if self.service else None,
                "service_endpoint": f"{config.name}.{config.namespace}.svc.cluster.local",
            }
        )

    def _create_deployment(self) -> k8s.apps.v1.Deployment:
        # Environment variables
        env_vars = []

        # Add plain env vars
        for key, value in self.config.container.env.items():
            env_vars.append(k8s.core.v1.EnvVarArgs(name=key, value=value))

        # Add secret-based env vars
        for env_name, secret_ref in self.config.container.env_from_secret.items():
            env_vars.append(
                k8s.core.v1.EnvVarArgs(
                    name=env_name,
                    value_from=k8s.core.v1.EnvVarSourceArgs(
                        secret_key_ref=k8s.core.v1.SecretKeySelectorArgs(
                            name=secret_ref, key=env_name
                        )
                    ),
                )
            )

        # Probes
        probes = {}
        if self.config.container.liveness_probe_path:
            probes["liveness_probe"] = k8s.core.v1.ProbeArgs(
                http_get=k8s.core.v1.HTTPGetActionArgs(
                    path=self.config.container.liveness_probe_path,
                    port=self.config.container.port,
                ),
                initial_delay_seconds=30,
                period_seconds=10,
            )

        if self.config.container.readiness_probe_path:
            probes["readiness_probe"] = k8s.core.v1.ProbeArgs(
                http_get=k8s.core.v1.HTTPGetActionArgs(
                    path=self.config.container.readiness_probe_path,
                    port=self.config.container.port,
                ),
                initial_delay_seconds=5,
                period_seconds=5,
            )

        return k8s.apps.v1.Deployment(
            f"{self.config.name}-deployment",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=self.config.name,
                namespace=self.config.namespace,
                labels=self._get_labels(),
                annotations=self.config.annotations,
            ),
            spec=k8s.apps.v1.DeploymentSpecArgs(
                replicas=self.config.replicas,
                selector=k8s.meta.v1.LabelSelectorArgs(
                    match_labels=self._get_match_labels()
                ),
                template=k8s.core.v1.PodTemplateSpecArgs(
                    metadata=k8s.meta.v1.ObjectMetaArgs(labels=self._get_labels()),
                    spec=k8s.core.v1.PodSpecArgs(
                        service_account_name=self.config.service_account,
                        image_pull_secrets=(
                            [
                                k8s.core.v1.LocalObjectReferenceArgs(
                                    name=secret_name,
                                )
                                for secret_name in self.config.container.image_pull_secrets
                            ]
                            if self.config.container.image_pull_secrets
                            else None
                        ),
                        containers=[
                            k8s.core.v1.ContainerArgs(
                                name=self.config.name,
                                image=self.config.container.image,
                                image_pull_policy=self.config.container.image_pull_policy,
                                ports=[
                                    k8s.core.v1.ContainerPortArgs(
                                        container_port=self.config.container.port
                                    )
                                ],
                                env=env_vars,
                                command=self.config.container.command,
                                args=self.config.container.args,
                                resources=k8s.core.v1.ResourceRequirementsArgs(
                                    requests=self.config.container.resources.get(
                                        "requests", {}
                                    ),
                                    limits=self.config.container.resources.get(
                                        "limits", {}
                                    ),
                                ),
                                **probes,
                            )
                        ],
                    ),
                ),
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

    def _create_service(self) -> k8s.core.v1.Service:
        return k8s.core.v1.Service(
            f"{self.config.name}-service",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=self.config.name,
                namespace=self.config.namespace,
                labels=self._get_labels(),
                annotations=self.config.service.annotations,
            ),
            spec=k8s.core.v1.ServiceSpecArgs(
                selector=self._get_match_labels(),
                ports=[
                    k8s.core.v1.ServicePortArgs(
                        port=self.config.service.port,
                        target_port=self.config.service.target_port
                        or self.config.container.port,
                    )
                ],
                type=self.config.service.type,
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

    def _create_ingress(self) -> k8s.networking.v1.Ingress:
        return k8s.networking.v1.Ingress(
            f"{self.config.name}-ingress",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=self.config.name,
                namespace=self.config.namespace,
                labels=self._get_labels(),
                annotations={
                    "kubernetes.io/ingress.class": "caddy",
                    **self.config.ingress.annotations,
                },
            ),
            spec=k8s.networking.v1.IngressSpecArgs(
                rules=[
                    k8s.networking.v1.IngressRuleArgs(
                        host=self.config.ingress.host,
                        http=k8s.networking.v1.HTTPIngressRuleValueArgs(
                            paths=[
                                k8s.networking.v1.HTTPIngressPathArgs(
                                    path=self.config.ingress.path,
                                    path_type="Prefix",
                                    backend=k8s.networking.v1.IngressBackendArgs(
                                        service=k8s.networking.v1.IngressServiceBackendArgs(
                                            name=self.config.name,
                                            port=k8s.networking.v1.ServiceBackendPortArgs(
                                                number=self.config.service.port
                                            ),
                                        )
                                    ),
                                )
                            ]
                        ),
                    )
                ]
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

    def _get_labels(self) -> Dict[str, str]:
        base_labels = {"App": self.config.name, "Version": "v1", "ManagedBy": "pulumi"}
        return {**base_labels, **self.config.labels}

    def _get_match_labels(self) -> Dict[str, str]:
        return {"App": self.config.name}
