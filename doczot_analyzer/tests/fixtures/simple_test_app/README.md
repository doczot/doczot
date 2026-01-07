# Simple Test API

A minimal FastAPI application for testing DocZot v3 features.

## Authentication

Authentication is performed via JWT tokens. Users must obtain a token by calling the login endpoint with valid credentials.

## Rate Limiting

Rate limiting protects the API from abuse. Each endpoint has specific rate limits based on the resource type.

## Projects

Projects are containers for organizing tasks and work items. Each project belongs to a single user and can contain multiple tasks.

## Items

Items are products available in the catalog. Each item has a name, description, and price.

## Users

Users are individuals who have accounts in the system. Each user can have multiple projects and preferences.
