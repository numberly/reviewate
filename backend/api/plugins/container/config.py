"""Configuration for the container plugin."""

from typing import Literal

from pydantic import BaseModel, Field


class WatcherConfig(BaseModel):
    """Configuration for the container watcher."""

    enabled: bool = Field(
        default=True,
        description="Run watcher in this process to monitor container status",
    )
    reconcile_interval: int = Field(
        default=60,
        description="Seconds between full reconciliation scans",
    )


class DockerConfig(BaseModel):
    """Docker-specific configuration."""

    socket: str = Field(
        default="/var/run/docker.sock",
        description="Path to Docker socket",
    )
    image: str = Field(
        default="reviewate/code-reviewer:latest",
        description="Docker image to use for code reviews",
    )
    network: str | None = Field(
        default=None,
        description="Docker network to attach containers to",
    )
    memory_limit: str = Field(
        default="2g",
        description="Memory limit for containers (e.g., '2g', '512m')",
    )
    cpu_limit: float = Field(
        default=2.0,
        description="CPU limit for containers (number of CPUs)",
    )
    timeout: int = Field(
        default=600,
        description="Maximum execution time in seconds (default 10 minutes)",
    )
    cleanup_containers: bool = Field(
        default=True,
        description="Whether to delete containers after completion (set to false for debugging)",
    )


class KubernetesConfig(BaseModel):
    """Kubernetes-specific configuration."""

    # Core
    namespace: str = Field(
        description="Kubernetes namespace for review jobs",
    )
    image: str = Field(
        default="reviewate/code-reviewer:latest",
        description="Container image to use for code reviews",
    )
    service_account: str = Field(
        description="Service account for review pods",
    )
    timeout: int = Field(
        default=600,
        description="Maximum execution time in seconds (activeDeadlineSeconds)",
    )

    # Resources
    memory_limit: str = Field(
        default="2Gi",
        description="Memory limit for pods",
    )
    memory_request: str = Field(
        default="512Mi",
        description="Memory request for pods",
    )
    cpu_limit: str = Field(
        default="2",
        description="CPU limit for pods",
    )
    cpu_request: str = Field(
        default="500m",
        description="CPU request for pods",
    )
    tmp_size_limit: str = Field(
        default="1Gi",
        description="Size limit for /tmp emptyDir volume (scratch space for repo cloning)",
    )

    # Image
    image_pull_policy: Literal["Always", "IfNotPresent", "Never"] = Field(
        default="IfNotPresent",
        description="Image pull policy for the container",
    )
    image_pull_secrets: list[str] = Field(
        default_factory=list,
        description="Image pull secret names (e.g., ['my-registry-secret'])",
    )

    # Scheduling
    node_selector: dict[str, str] = Field(
        default_factory=dict,
        description="Node selector labels (e.g., {'workload': 'review'})",
    )
    tolerations: list[dict[str, str]] = Field(
        default_factory=list,
        description="Kubernetes toleration objects",
    )
    annotations: dict[str, str] = Field(
        default_factory=dict,
        description="Pod annotations (e.g., Istio, Vault injection)",
    )

    # Security
    run_as_user: int = Field(
        default=1000,
        description="UID to run the pod as",
    )
    run_as_group: int = Field(
        default=1000,
        description="GID to run the pod as",
    )

    # Lifecycle
    cleanup_jobs: bool = Field(
        default=True,
        description="Delete Jobs after completion (set to false for debugging)",
    )


class ContainerPluginConfig(BaseModel):
    """Configuration for the container plugin."""

    enabled: bool = Field(
        default=False,
        description="Enable the container plugin",
    )
    backend: Literal["docker", "kubernetes"] = Field(
        default="docker",
        description="Container backend to use",
    )
    watcher: WatcherConfig = Field(
        default_factory=WatcherConfig,
        description="Watcher configuration",
    )
    docker: DockerConfig | None = Field(
        default_factory=DockerConfig,
        description="Docker-specific configuration",
    )
    kubernetes: KubernetesConfig | None = Field(
        default=None,
        description="Kubernetes-specific configuration",
    )
