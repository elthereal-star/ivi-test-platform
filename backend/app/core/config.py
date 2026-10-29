from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全部通过环境变量注入，默认值仅供本地开发使用。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "车机测试数据平台"
    API_V1: str = "/api/v1"
    ENV: str = "dev"

    # 数据库
    DATABASE_URL: str = "postgresql+psycopg://ivi:ivi@localhost:5432/ivi_test"

    # 鉴权
    SECRET_KEY: str = "dev-only-secret-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

    # 自动化脚本回传用的静态令牌（服务账号，不走 JWT）
    AUTOMATION_TOKEN: str = "dev-automation-token"

    # LLM：任何 OpenAI 兼容网关都行（DeepSeek / Qwen / vLLM）
    AI_BASE_URL: str = ""
    AI_API_KEY: str = ""
    AI_MODEL: str = "deepseek-chat"
    AI_TIMEOUT_S: int = 60

    # 演示数据
    SEED_ON_STARTUP: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
