import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s
from tools.loader import load_service_configs
from tools.envs import load_env_secrets
from modules.ingress import create_on_demand_service, create_caddy
from modules.apps.webservice import WebService


def create_bonde_org_env():
    """
    Stack BONDE-ORG: Ambiente completo com conexão automática ALB → Caddy
    """
    stack_name = pulumi.get_stack()

    shared_stack = pulumi.StackReference("nossas/infra-eks/shared")
    kubeconfig = shared_stack.get_output("kubeconfig")

    k8s_provider = k8s.Provider(f"k8s-{stack_name}", kubeconfig=kubeconfig)

    namespace = k8s.core.v1.Namespace(
        f"{stack_name}-ns",
        metadata=k8s.meta.v1.ObjectMetaArgs(name=stack_name),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )
    
    load_env_secrets(namespace=namespace, provider=k8s_provider)

    pulumi.log.info("Criando serviço on-demand para verificação TLS...")
    on_demand_service = create_on_demand_service(
        "on-demand",
        namespace=namespace,
        k8s_provider=k8s_provider,
        environment=stack_name,
    )

    # pulumi.log.info("Criando S3 Bucket para armazenamento de certificados...")
    # account_id = aws.get_caller_identity().account_id
    # bucket = aws.s3.Bucket(
    #     "caddy-certs-bonde-org",
    #     bucket=f"caddy-certificates-bonde-org-{account_id}",
    #     force_destroy=True,
    #     # ✅ Tudo configurado aqui
    #     versioning=aws.s3.BucketVersioningArgs(enabled=True),
    #     server_side_encryption_configuration=aws.s3.BucketServerSideEncryptionConfigurationArgs(
    #         rule=aws.s3.BucketServerSideEncryptionConfigurationRuleArgs(
    #             apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationRuleApplyServerSideEncryptionByDefaultArgs(
    #                 sse_algorithm="AES256",
    #             ),
    #         ),
    #     ),
    # )

    # # ✅ Apenas isto separado
    # aws.s3.BucketPublicAccessBlock(
    #     "caddy-certs-block-public",
    #     bucket=bucket.id,
    #     block_public_acls=True,
    #     block_public_policy=True,
    #     ignore_public_acls=True,
    #     restrict_public_buckets=True,
    # )

    pulumi.log.info("Criando Caddy Ingress + NLB AWS...")
    caddy = create_caddy(
        name="caddy",
        namespace=stack_name,
        k8s_provider=k8s_provider,
        environment=stack_name,
        # s3_bucket_name=bucket.bucket,  # ✅ Já é um Output
        # use_s3_for_certificates=True,
        # replicas=1,
        # aws_region="us-east-1",
        resources={
            "requests": {"memory": "500Mi", "cpu": "10m"},
            "limits": {"memory": "800Mi", "cpu": "50m"},
        },
    )

    service_loaded_configs = load_service_configs(environment=stack_name)
    created_services = {}

    for service_name, service_config in service_loaded_configs.items():
        pulumi.log.info(f"🎯 Criando serviço: {service_name}")

        service = WebService(
            service_name,
            config=service_config,
            opts=pulumi.ResourceOptions(
                provider=k8s_provider,
                depends_on=[namespace, caddy, on_demand_service],
                # custom_timeouts=pulumi.CustomTimeouts(create="10m")
            ),
        )
        created_services[service_name] = service

    pulumi.export("namespace", namespace.metadata["name"])
    pulumi.export("caddy_url", caddy.load_balancer_url)
    # # pulumi.export("s3_bucket", bucket.bucket)
    pulumi.log.info(f"{stack_name} com NetworkLoadBalancer automático!")
