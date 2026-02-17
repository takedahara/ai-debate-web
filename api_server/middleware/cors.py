"""CORS configuration"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def setup_cors(app: FastAPI) -> None:
    """Configure CORS middleware

    Reads ALLOWED_ORIGINS from environment variable.
    Default: allows all origins for simplicity (can be restricted in production)
    """
    origins_str = os.getenv("ALLOWED_ORIGINS", "")

    if origins_str:
        # 環境変数で指定されている場合はそれを使用
        origins = [origin.strip() for origin in origins_str.split(",") if origin.strip()]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )
    else:
        # 指定がない場合は全てのオリジンを許可（開発・デモ用）
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,  # allow_origins=["*"]の場合はFalseにする必要がある
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )
