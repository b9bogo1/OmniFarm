"""OpenAPI 3.0 spec for OmniFarm Hub REST API v1."""


def get_spec() -> dict:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "OmniFarm Hub API",
            "version": "1.0.0",
            "description": (
                "REST API for OmniFarm Hub — agricultural management and e-commerce platform. "
                "Authenticate via `/api/v1/auth/token` to receive a Bearer token, "
                "then pass it as `Authorization: Bearer <token>` on protected endpoints."
            ),
            "contact": {"name": "OmniFarm Support"},
        },
        "servers": [{"url": "/api/v1", "description": "Current server"}],
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            },
            "schemas": {
                "Error": {
                    "type": "object",
                    "properties": {"error": {"type": "string"}},
                },
                "Product": {
                    "type": "object",
                    "properties": {
                        "id":             {"type": "string"},
                        "name":           {"type": "string"},
                        "description":    {"type": "string", "nullable": True},
                        "category":       {"type": "string", "enum": ["fish", "poultry", "rabbit", "eggs", "other"]},
                        "category_label": {"type": "string"},
                        "category_icon":  {"type": "string"},
                        "price_xaf":      {"type": "number"},
                        "unit":           {"type": "string"},
                        "stock_quantity": {"type": "number"},
                        "is_available":   {"type": "boolean"},
                        "image_url":      {"type": "string", "nullable": True},
                        "created_at":     {"type": "string", "format": "date-time"},
                    },
                },
                "OrderItem": {
                    "type": "object",
                    "properties": {
                        "product_name":   {"type": "string"},
                        "product_unit":   {"type": "string"},
                        "unit_price_xaf": {"type": "number"},
                        "quantity":       {"type": "number"},
                        "subtotal_xaf":   {"type": "number"},
                    },
                },
                "Order": {
                    "type": "object",
                    "properties": {
                        "order_number":     {"type": "string"},
                        "status":           {"type": "string"},
                        "status_label":     {"type": "string"},
                        "payment_method":   {"type": "string", "nullable": True},
                        "total_xaf":        {"type": "number"},
                        "customer_name":    {"type": "string"},
                        "customer_phone":   {"type": "string"},
                        "customer_address": {"type": "string", "nullable": True},
                        "notes":            {"type": "string", "nullable": True},
                        "created_at":       {"type": "string", "format": "date-time"},
                        "items":            {"type": "array", "items": {"$ref": "#/components/schemas/OrderItem"}},
                    },
                },
                "TokenRequest": {
                    "type": "object",
                    "required": ["username", "password"],
                    "properties": {
                        "username": {"type": "string", "description": "Username or e-mail"},
                        "password": {"type": "string", "format": "password"},
                    },
                },
                "CreateOrderRequest": {
                    "type": "object",
                    "required": ["customer_name", "customer_phone", "items"],
                    "properties": {
                        "customer_name":    {"type": "string"},
                        "customer_phone":   {"type": "string"},
                        "customer_address": {"type": "string"},
                        "notes":            {"type": "string"},
                        "payment_method":   {
                            "type": "string",
                            "enum": ["orange_money", "mtn_mobile_money", "cash_on_delivery"],
                            "default": "cash_on_delivery",
                        },
                        "mobile_money_phone": {"type": "string"},
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["product_id", "quantity"],
                                "properties": {
                                    "product_id": {"type": "string"},
                                    "quantity":   {"type": "number", "minimum": 0.1},
                                },
                            },
                        },
                    },
                },
            },
        },
        "paths": {
            "/status": {
                "get": {
                    "summary": "API health check",
                    "operationId": "getStatus",
                    "tags": ["System"],
                    "responses": {
                        "200": {
                            "description": "API is up",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status":    {"type": "string"},
                                            "version":   {"type": "string"},
                                            "timestamp": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/auth/token": {
                "post": {
                    "summary": "Obtain JWT access + refresh tokens",
                    "operationId": "authToken",
                    "tags": ["Auth"],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/TokenRequest"}}},
                    },
                    "responses": {
                        "200": {
                            "description": "Tokens issued",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "access_token":  {"type": "string"},
                                            "refresh_token": {"type": "string"},
                                            "token_type":    {"type": "string"},
                                            "user": {
                                                "type": "object",
                                                "properties": {
                                                    "id":       {"type": "string"},
                                                    "username": {"type": "string"},
                                                    "email":    {"type": "string"},
                                                    "role":     {"type": "string"},
                                                },
                                            },
                                        },
                                    }
                                }
                            },
                        },
                        "401": {"description": "Invalid credentials", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
                    },
                }
            },
            "/auth/refresh": {
                "post": {
                    "summary": "Refresh access token",
                    "operationId": "authRefresh",
                    "tags": ["Auth"],
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "New access token",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "access_token": {"type": "string"},
                                            "token_type":   {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/products": {
                "get": {
                    "summary": "List available products",
                    "operationId": "listProducts",
                    "tags": ["Products"],
                    "parameters": [
                        {"name": "q",         "in": "query", "schema": {"type": "string"},  "description": "Search query"},
                        {"name": "category",  "in": "query", "schema": {"type": "string"},  "description": "Filter by category (fish, poultry, rabbit, eggs, other)"},
                        {"name": "min_price", "in": "query", "schema": {"type": "number"},  "description": "Minimum price in XAF"},
                        {"name": "max_price", "in": "query", "schema": {"type": "number"},  "description": "Maximum price in XAF"},
                        {"name": "page",      "in": "query", "schema": {"type": "integer", "default": 1}},
                        {"name": "per_page",  "in": "query", "schema": {"type": "integer", "default": 20, "maximum": 100}},
                    ],
                    "responses": {
                        "200": {
                            "description": "Paginated product list",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "products": {"type": "array", "items": {"$ref": "#/components/schemas/Product"}},
                                            "total":    {"type": "integer"},
                                            "page":     {"type": "integer"},
                                            "per_page": {"type": "integer"},
                                            "pages":    {"type": "integer"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/products/{product_id}": {
                "get": {
                    "summary": "Get a single product",
                    "operationId": "getProduct",
                    "tags": ["Products"],
                    "parameters": [{"name": "product_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {
                        "200": {
                            "description": "Product details",
                            "content": {"application/json": {"schema": {"type": "object", "properties": {"product": {"$ref": "#/components/schemas/Product"}}}}},
                        },
                        "404": {"description": "Not found", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
                    },
                }
            },
            "/orders": {
                "get": {
                    "summary": "List my orders",
                    "operationId": "listOrders",
                    "tags": ["Orders"],
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "Order list",
                            "content": {"application/json": {"schema": {"type": "object", "properties": {"orders": {"type": "array", "items": {"$ref": "#/components/schemas/Order"}}}}}},
                        }
                    },
                },
                "post": {
                    "summary": "Create a new order",
                    "operationId": "createOrder",
                    "tags": ["Orders"],
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/CreateOrderRequest"}}},
                    },
                    "responses": {
                        "201": {
                            "description": "Order created",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "order":       {"$ref": "#/components/schemas/Order"},
                                            "payment_url": {"type": "string", "description": "Redirect URL for Orange Money"},
                                        },
                                    }
                                }
                            },
                        },
                        "400": {"description": "Validation error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
                        "409": {"description": "Insufficient stock", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
                    },
                },
            },
            "/orders/{order_number}": {
                "get": {
                    "summary": "Get order details",
                    "operationId": "getOrder",
                    "tags": ["Orders"],
                    "security": [{"BearerAuth": []}],
                    "parameters": [{"name": "order_number", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {
                        "200": {
                            "description": "Order with items",
                            "content": {"application/json": {"schema": {"type": "object", "properties": {"order": {"$ref": "#/components/schemas/Order"}}}}},
                        },
                        "403": {"description": "Access denied"},
                        "404": {"description": "Not found"},
                    },
                }
            },
        },
        "tags": [
            {"name": "System",   "description": "Health and status"},
            {"name": "Auth",     "description": "Authentication — JWT tokens"},
            {"name": "Products", "description": "Product catalog (public)"},
            {"name": "Orders",   "description": "Order management (requires auth)"},
        ],
    }
