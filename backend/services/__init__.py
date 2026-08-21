"""Services package for business logic and domain operations.

Import concrete services from their modules. Keeping package initialization
side-effect free prevents unrelated converters from loading optional runtime
dependencies during API startup and focused tests.
"""
