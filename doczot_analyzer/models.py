"""Data models for DocZot analyzer.

This module defines Pydantic v2 models for representing:
- API endpoints detected in code
- Documentation references found in markdown
- Analysis results and reports
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class Parameter(BaseModel):
    """Represents a function parameter in an API endpoint.

    Attributes:
        name: Parameter name (e.g., "user_id")
        type_hint: Type annotation as string (e.g., "int", "str", "UserCreate")
        location: Where the parameter is used ("path", "query", "body", "header")
        required: Whether the parameter is required (no default value)
        default_value: Default value if parameter is optional (None if required)
    """
    name: str
    type_hint: Optional[str] = None
    location: str = "query"  # Default to query parameter
    required: bool = True
    default_value: Optional[str] = None

    def __str__(self) -> str:
        """String representation of parameter."""
        required_str = "required" if self.required else f"default={self.default_value}"
        type_str = f": {self.type_hint}" if self.type_hint else ""
        return f"{self.name}{type_str} ({self.location}, {required_str})"

    def __hash__(self) -> int:
        """Hash for use in sets/dicts."""
        return hash((self.name, self.type_hint, self.location))


class Endpoint(BaseModel):
    """Represents a detected FastAPI endpoint.

    Based on endpoint-detection.md specification R3.

    Attributes:
        method: HTTP method (GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD)
        path: URL path including parameters (e.g., "/users/{user_id}")
        function_name: Name of the Python function handling this endpoint
        file_path: Path to the file containing this endpoint
        line_number: Line number where the endpoint is defined
        docstring: Function docstring if present
        has_docstring: Whether the function has a docstring
        parameters: List of function parameters
        response_model: Response model type if specified in decorator
        is_deprecated: Whether endpoint is marked as deprecated
        is_async: Whether the handler function is async
        is_documented: Whether this endpoint is found in documentation (set during analysis)
    """
    method: str
    path: str
    function_name: str
    file_path: str
    line_number: int
    docstring: Optional[str] = None
    has_docstring: bool = False
    parameters: List[Parameter] = Field(default_factory=list)
    response_model: Optional[str] = None
    is_deprecated: bool = False
    is_async: bool = False
    is_documented: bool = False

    def __str__(self) -> str:
        """String representation of endpoint."""
        deprecated = " [DEPRECATED]" if self.is_deprecated else ""
        documented = " " if self.is_documented else " "
        return f"{self.method} {self.path} -> {self.function_name}(){deprecated}{documented}"

    def __hash__(self) -> int:
        """Hash for use in sets/dicts."""
        return hash((self.method, self.path, self.file_path))

    @property
    def route_signature(self) -> str:
        """Return a unique signature for this route (method + path)."""
        return f"{self.method} {self.path}"


class DocReference(BaseModel):
    """Represents an API endpoint reference found in markdown documentation.

    Based on documentation-parsing.md specification R3.

    Attributes:
        file_path: Path to the markdown file
        content: The text content containing the reference
        mentioned_paths: List of endpoint paths found (e.g., ["/users", "/users/{id}"])
        mentioned_methods: List of HTTP methods found (e.g., ["GET", "POST"])
        section_heading: The markdown section heading (## or ###) above this reference
        line_number: Line number where the reference appears
    """
    file_path: str
    content: str
    mentioned_paths: List[str] = Field(default_factory=list)
    mentioned_methods: List[str] = Field(default_factory=list)
    section_heading: Optional[str] = None
    line_number: int = 1

    def __str__(self) -> str:
        """String representation of documentation reference."""
        section = f" (in '{self.section_heading}')" if self.section_heading else ""
        methods = ", ".join(self.mentioned_methods) if self.mentioned_methods else "no methods"
        paths = ", ".join(self.mentioned_paths) if self.mentioned_paths else "no paths"
        return f"{self.file_path}:{self.line_number}{section} - {methods}: {paths}"

    def __hash__(self) -> int:
        """Hash for use in sets/dicts."""
        return hash((self.file_path, self.line_number, tuple(self.mentioned_paths)))

    def matches_endpoint(self, endpoint: Endpoint) -> bool:
        """Check if this documentation reference matches an endpoint.

        Args:
            endpoint: The endpoint to check against

        Returns:
            True if this doc reference mentions the endpoint's method and path
        """
        method_match = endpoint.method in self.mentioned_methods
        path_match = endpoint.path in self.mentioned_paths
        return method_match and path_match


class ScanResult(BaseModel):
    """Result of scanning a codebase for endpoints.

    Attributes:
        endpoints: List of detected endpoints
        total_endpoints: Count of total endpoints found
        files_scanned: List of file paths that were scanned
    """
    endpoints: List[Endpoint] = Field(default_factory=list)
    total_endpoints: int = 0
    files_scanned: List[str] = Field(default_factory=list)

    def __str__(self) -> str:
        """String representation of scan result."""
        return f"Scanned {len(self.files_scanned)} files, found {self.total_endpoints} endpoints"

    def model_post_init(self, __context) -> None:
        """Update total_endpoints after initialization."""
        self.total_endpoints = len(self.endpoints)


class AnalysisReport(BaseModel):
    """Final analysis report comparing code and documentation.

    Attributes:
        total_endpoints: Total number of endpoints found in code
        documented_endpoints: Number of endpoints with documentation
        undocumented_endpoints: Number of endpoints without documentation
        coverage_percentage: Percentage of endpoints that are documented (0-100)
        endpoints: List of all endpoints with documentation status
        repository: Repository path or URL (optional)
        commit_sha: Git commit SHA for this analysis (optional)
    """
    total_endpoints: int
    documented_endpoints: int = 0
    undocumented_endpoints: int = 0
    coverage_percentage: float = 0.0
    endpoints: List[Endpoint] = Field(default_factory=list)
    repository: Optional[str] = None
    commit_sha: Optional[str] = None

    def __str__(self) -> str:
        """String representation of analysis report."""
        return (
            f"Documentation Coverage: {self.coverage_percentage:.1f}% "
            f"({self.documented_endpoints}/{self.total_endpoints} endpoints documented)"
        )

    def model_post_init(self, __context) -> None:
        """Calculate derived fields after initialization."""
        self.total_endpoints = len(self.endpoints)
        self.documented_endpoints = sum(1 for ep in self.endpoints if ep.is_documented)
        self.undocumented_endpoints = self.total_endpoints - self.documented_endpoints

        if self.total_endpoints > 0:
            self.coverage_percentage = (self.documented_endpoints / self.total_endpoints) * 100
        else:
            self.coverage_percentage = 0.0

    @property
    def undocumented_endpoint_list(self) -> List[Endpoint]:
        """Get list of endpoints that lack documentation."""
        return [ep for ep in self.endpoints if not ep.is_documented]

    @property
    def documented_endpoint_list(self) -> List[Endpoint]:
        """Get list of endpoints that have documentation."""
        return [ep for ep in self.endpoints if ep.is_documented]
