# Terraform Configuration for vMiner Hyper-Scale Deployment
# Provider: AWS
# Architecture: Distributed with PostgreSQL, Redis, RabbitMQ

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket = "vminer-terraform-state"
    key    = "production/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# Variables
variable "aws_region" {
  description = "AWS region"
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  default     = "production"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  default     = "10.0.0.0/16"
}

# VPC Configuration
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "vminer-vpc-${var.environment}"
    Environment = var.environment
  }
}

# Public Subnets (for Load Balancer)
resource "aws_subnet" "public" {
  count             = 3
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 1}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name        = "vminer-public-${count.index + 1}"
    Environment = var.environment
  }
}

# Private Subnets (for API servers, DB, etc.)
resource "aws_subnet" "private" {
  count             = 3
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 10}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name        = "vminer-private-${count.index + 1}"
    Environment = var.environment
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name        = "vminer-igw"
    Environment = var.environment
  }
}

# NAT Gateway
resource "aws_eip" "nat" {
  count  = 3
  domain = "vpc"

  tags = {
    Name        = "vminer-nat-eip-${count.index + 1}"
    Environment = var.environment
  }
}

resource "aws_nat_gateway" "main" {
  count         = 3
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = {
    Name        = "vminer-nat-${count.index + 1}"
    Environment = var.environment
  }
}

# Route Tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name        = "vminer-public-rt"
    Environment = var.environment
  }
}

resource "aws_route_table" "private" {
  count  = 3
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }

  tags = {
    Name        = "vminer-private-rt-${count.index + 1}"
    Environment = var.environment
  }
}

# Security Groups
resource "aws_security_group" "alb" {
  name        = "vminer-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "vminer-alb-sg"
    Environment = var.environment
  }
}

resource "aws_security_group" "api_servers" {
  name        = "vminer-api-sg"
  description = "Security group for API servers"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "vminer-api-sg"
    Environment = var.environment
  }
}

resource "aws_security_group" "database" {
  name        = "vminer-db-sg"
  description = "Security group for PostgreSQL"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.api_servers.id]
  }

  tags = {
    Name        = "vminer-db-sg"
    Environment = var.environment
  }
}

# RDS PostgreSQL Cluster
resource "aws_db_subnet_group" "main" {
  name       = "vminer-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = {
    Name        = "vminer-db-subnet-group"
    Environment = var.environment
  }
}

resource "aws_rds_cluster" "postgresql" {
  cluster_identifier      = "vminer-postgres-cluster"
  engine                  = "aurora-postgresql"
  engine_version          = "15.4"
  database_name           = "vminer"
  master_username         = "vminer_admin"
  master_password         = var.db_password # Use AWS Secrets Manager in production
  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [aws_security_group.database.id]
  backup_retention_period = 7
  preferred_backup_window = "03:00-04:00"
  skip_final_snapshot     = false
  final_snapshot_identifier = "vminer-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  
  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = {
    Name        = "vminer-postgres-cluster"
    Environment = var.environment
  }
}

# Primary Instance
resource "aws_rds_cluster_instance" "primary" {
  identifier         = "vminer-postgres-primary"
  cluster_identifier = aws_rds_cluster.postgresql.id
  instance_class     = "db.r5.4xlarge"
  engine             = aws_rds_cluster.postgresql.engine
  engine_version     = aws_rds_cluster.postgresql.engine_version

  performance_insights_enabled = true
  monitoring_interval          = 60
  monitoring_role_arn          = aws_iam_role.rds_monitoring.arn

  tags = {
    Name        = "vminer-postgres-primary"
    Environment = var.environment
  }
}

# Read Replicas
resource "aws_rds_cluster_instance" "replica" {
  count              = 3
  identifier         = "vminer-postgres-replica-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.postgresql.id
  instance_class     = "db.r5.2xlarge"
  engine             = aws_rds_cluster.postgresql.engine
  engine_version     = aws_rds_cluster.postgresql.engine_version

  performance_insights_enabled = true

  tags = {
    Name        = "vminer-postgres-replica-${count.index + 1}"
    Environment = var.environment
  }
}

# ElastiCache Redis
resource "aws_elasticache_subnet_group" "main" {
  name       = "vminer-redis-subnet-group"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "vminer-redis"
  replication_group_description = "Redis cluster for vMiner caching"
  engine                     = "redis"
  engine_version             = "7.0"
  node_type                  = "cache.r5.xlarge"
  num_cache_clusters         = 3
  parameter_group_name       = "default.redis7"
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.api_servers.id]
  automatic_failover_enabled = true
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  tags = {
    Name        = "vminer-redis"
    Environment = var.environment
  }
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "vminer-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = true
  enable_http2              = true

  tags = {
    Name        = "vminer-alb"
    Environment = var.environment
  }
}

resource "aws_lb_target_group" "api" {
  name     = "vminer-api-tg"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }

  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400
    enabled         = true
  }

  tags = {
    Name        = "vminer-api-tg"
    Environment = var.environment
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = var.ssl_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# Auto Scaling Group for API Servers
resource "aws_launch_template" "api_server" {
  name_prefix   = "vminer-api-"
  image_id      = var.api_server_ami
  instance_type = "c5.2xlarge"

  vpc_security_group_ids = [aws_security_group.api_servers.id]

  user_data = base64encode(templatefile("${path.module}/user_data/api_server.sh", {
    db_host     = aws_rds_cluster.postgresql.endpoint
    redis_host  = aws_elasticache_replication_group.redis.primary_endpoint_address
    environment = var.environment
  }))

  iam_instance_profile {
    name = aws_iam_instance_profile.api_server.name
  }

  monitoring {
    enabled = true
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name        = "vminer-api-server"
      Environment = var.environment
    }
  }
}

resource "aws_autoscaling_group" "api_servers" {
  name                = "vminer-api-asg"
  vpc_zone_identifier = aws_subnet.private[*].id
  target_group_arns   = [aws_lb_target_group.api.arn]
  health_check_type   = "ELB"
  health_check_grace_period = 300

  min_size         = 5
  max_size         = 20
  desired_capacity = 5

  launch_template {
    id      = aws_launch_template.api_server.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "vminer-api-server"
    propagate_at_launch = true
  }
}

# Auto Scaling Policies
resource "aws_autoscaling_policy" "scale_up" {
  name                   = "vminer-api-scale-up"
  scaling_adjustment     = 2
  adjustment_type        = "ChangeInCapacity"
  cooldown               = 300
  autoscaling_group_name = aws_autoscaling_group.api_servers.name
}

resource "aws_autoscaling_policy" "scale_down" {
  name                   = "vminer-api-scale-down"
  scaling_adjustment     = -1
  adjustment_type        = "ChangeInCapacity"
  cooldown               = 300
  autoscaling_group_name = aws_autoscaling_group.api_servers.name
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "vminer-api-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "70"
  alarm_description   = "This metric monitors API server CPU utilization"
  alarm_actions       = [aws_autoscaling_policy.scale_up.arn]

  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.api_servers.name
  }
}

# IAM Roles
resource "aws_iam_role" "api_server" {
  name = "vminer-api-server-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_instance_profile" "api_server" {
  name = "vminer-api-server-profile"
  role = aws_iam_role.api_server.name
}

resource "aws_iam_role" "rds_monitoring" {
  name = "vminer-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# Outputs
output "alb_dns_name" {
  description = "DNS name of the load balancer"
  value       = aws_lb.main.dns_name
}

output "rds_endpoint" {
  description = "PostgreSQL cluster endpoint"
  value       = aws_rds_cluster.postgresql.endpoint
}

output "redis_endpoint" {
  description = "Redis primary endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

# Variables file
variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}

variable "ssl_certificate_arn" {
  description = "ARN of SSL certificate"
  type        = string
}

variable "api_server_ami" {
  description = "AMI ID for API servers"
  type        = string
}
