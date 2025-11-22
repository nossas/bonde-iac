import pulumi
import pulumi_aws as aws


class LoadBalancerStack(pulumi.ComponentResource):
    """
    LoadBalancerStack cria um Application Load Balancer específico por ambiente.

    USO:
    - Stack SANDBOX: ALB para ambiente de desenvolvimento
    - Stack PRODUCTION: ALB para ambiente de produção

    CARACTERÍSTICAS:
    - ALB público na porta 80
    - Target Group com tipo IP para EKS
    - Health checks básicos
    - Tags específicas por ambiente
    """

    def __init__(
        self,
        name: str,
        vpc_id: pulumi.Input[str],
        public_subnet_ids: pulumi.Input[list],
        opts=None,
    ):
        super().__init__("custom:lb:LoadBalancerStack", name, None, opts)

        config = pulumi.Config("infra-eks")
        environment = config.require("environment")

        # Security Group para o ALB
        self.alb_security_group = aws.ec2.SecurityGroup(
            f"alb-sg-{environment}",
            description=f"Security Group para ALB - {environment}",
            vpc_id=vpc_id,
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    protocol="tcp",
                    from_port=80,
                    to_port=80,
                    cidr_blocks=["0.0.0.0/0"],
                    description="HTTP from Internet",
                )
            ],
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    protocol="-1",
                    from_port=0,
                    to_port=0,
                    cidr_blocks=["0.0.0.0/0"],
                    description="Allow all outbound",
                )
            ],
            tags={
                "Name": f"alb-sg-{environment}",
                "Environment": environment,
                "ManagedBy": "pulumi",
            },
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Application Load Balancer
        self.alb = aws.lb.LoadBalancer(
            f"alb-{environment}",
            name=f"alb-{environment}",
            internal=False,
            load_balancer_type="application",
            security_groups=[self.alb_security_group.id],
            subnets=public_subnet_ids,
            enable_deletion_protection=False,
            idle_timeout=60,
            tags={
                "Name": f"alb-{environment}",
                "Environment": environment,
                "ManagedBy": "pulumi",
                "Purpose": "eks-ingress",
            },
            opts=pulumi.ResourceOptions(
                parent=self, depends_on=[self.alb_security_group]
            ),
        )

        # Target Group para EKS (tipo IP)
        self.target_group = aws.lb.TargetGroup(
            f"tg-{environment}",
            name=f"tg-{environment}",
            port=80,
            protocol="HTTP",
            vpc_id=vpc_id,
            target_type="instance",
            health_check=aws.lb.TargetGroupHealthCheckArgs(
                enabled=True,
                path="/",
                protocol="HTTP",
                port="traffic-port",
                healthy_threshold=2,
                unhealthy_threshold=2,
                timeout=5,
                interval=30,
                matcher="200-399",
            ),
            tags={
                "Name": f"tg-{environment}",
                "Environment": environment,
                "Purpose": "caddy-proxy",
            },
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Listener HTTP
        self.listener = aws.lb.Listener(
            f"listener-{environment}",
            load_balancer_arn=self.alb.arn,
            port=80,
            protocol="HTTP",
            default_actions=[
                aws.lb.ListenerDefaultActionArgs(
                    type="forward", target_group_arn=self.target_group.arn
                )
            ],
            tags={"Environment": environment},
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.target_group]),
        )

        # Export dos outputs
        self.alb_dns_name = self.alb.dns_name
        self.alb_zone_id = self.alb.zone_id
        self.load_balancer_arn = self.alb.arn
        self.target_group_arn = self.target_group.arn

        self.register_outputs(
            {
                "alb_dns_name": self.alb_dns_name,
                "alb_zone_id": self.alb_zone_id,
                "load_balancer_arn": self.alb.arn,
                "target_group_arn": self.target_group.arn,
                "alb_url": pulumi.Output.concat("http://", self.alb_dns_name),
            }
        )


def create_load_balancer(
    name: str, vpc_id: pulumi.Input[str], public_subnet_ids: pulumi.Input[list]
):
    """
    Cria um Load Balancer específico para um ambiente.

    Args:
        name: Nome do componente
        vpc_id: ID da VPC compartilhada
        public_subnet_ids: IDs das subnets públicas para o ALB

    Returns:
        LoadBalancerStack: Instância do ALB criado
    """
    return LoadBalancerStack(name, vpc_id, public_subnet_ids)
