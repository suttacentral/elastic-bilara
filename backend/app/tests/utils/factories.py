import random


class ProjectFactory:
    @staticmethod
    def create_project(**kwargs):
        default_data = {
            "project_uid": f"project{random.randint(1, 1000)}",
            "name": f"Project {random.randint(1, 1000)}",
            "root_path": f"root/path{random.randint(1, 1000)}",
            "translation_path": f"translation/path{random.randint(1, 1000)}",
            "translation_muids": f"translation-en-user{random.randint(1, 1000)}",
            "creator_github_handle": f"user{random.randint(1, 1000)}",
        }
        return {**default_data, **kwargs}

    @staticmethod
    def create_projects(n, **kwargs):
        return [
            ProjectFactory.create_project(
                **{k: v[i] if isinstance(v, list) and i < len(v) else v for k, v in kwargs.items()}
            )
            for i in range(n)
        ]


class PublicationFactory:
    @staticmethod
    def create_publication(**kwargs):
        default_data = {
            "publication_number": f"pub{random.randint(1, 1000)}",
            "root_lang_iso": "pli",
            "root_lang_name": "Pali",
            "translation_lang_iso": "en",
            "translation_lang_name": "English",
            "source_url": "https://test.com",
            "creator_uid": "test",
            "creator_name": "Test",
            "creator_github_handle": "test",
            "text_uid": "mil",
            "translation_title": "Test Translation Title",
            "translation_subtitle": "Test Subtitle",
            "root_title": "Test Root Title",
            "creation_process": "Test Creation Process",
            "text_description": "Test Text Description",
            "is_published": True,
            "publication_status": "Test Publication Status",
            "license_type": "Creative Commons Zero",
            "license_abbreviation": "CC0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "license_statement": "Test License Statement",
            "first_published": "2023",
            "editions_url": "https://test.com/test",
        }
        return {**default_data, **kwargs}

    @staticmethod
    def create_publications(n, **kwargs):
        return [
            PublicationFactory.create_publication(
                **{k: v[i] if isinstance(v, list) and i < len(v) else v for k, v in kwargs.items()}
            )
            for i in range(n)
        ]
