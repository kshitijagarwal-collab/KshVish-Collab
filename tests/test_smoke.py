def test_repo_imports_resolve() -> None:
    import src.core.domain.kyc_case  # noqa: F401
    import src.core.domain.applicant  # noqa: F401
    import src.core.domain.document  # noqa: F401
