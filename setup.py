from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="terraform-aws-migrator",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "python-hcl2",
        "boto3",
        "rich",
    ],
    entry_points={
        'console_scripts': [
            'tfawsmigrator=terraform_aws_migrator.main:main',
        ],
    },
    author="Your Name",
    author_email="your.email@example.com",
    description="A tool to migrate unmanaged AWS resources to Terraform",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/terraform-aws-migrator",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)
