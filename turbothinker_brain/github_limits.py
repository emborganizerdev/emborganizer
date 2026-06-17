NORMAL_GIT_FILE_LIMIT_MB = 100
RECOMMENDED_REPO_MAX_GB = 1
STRONGLY_RECOMMENDED_REPO_MAX_GB = 5
RECOMMENDED_MODEL_SHARD_MB = 24


def github_safe_storage_advice() -> dict:
    return {
        'normal_git_single_file_limit_mb': NORMAL_GIT_FILE_LIMIT_MB,
        'recommended_repo_max_gb': RECOMMENDED_REPO_MAX_GB,
        'strongly_recommended_repo_max_gb': STRONGLY_RECOMMENDED_REPO_MAX_GB,
        'recommended_model_brain_part_mb': RECOMMENDED_MODEL_SHARD_MB,
        'max_brain_part_mb': 25,
        'keep_local_not_git': ['raw image zips', 'embroidery libraries', 'generated cache', 'large binary model files'],
    }
