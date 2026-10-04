"""Site-specific evidence cannot extend the protected publication registry."""
import unittest

from esports_data.review_safety import require_authority


class SiteEvidenceAuthorityTests(unittest.TestCase):
    def test_registered_site_publishers_have_exact_host_authority(self):
        for publisher, url in (
            ('kespa-school', 'https://school.e-sports.or.kr/notice/view/1123'),
            ('inu', 'https://www.inu.ac.kr/bbs/inu/2611/430031/artclView.do'),
        ):
            require_authority({'evidence': [{'publisher_id': publisher, 'url': url}]})

    def test_wrong_publisher_subdomains_and_lookalikes_are_rejected(self):
        for publisher, url in (
            ('moe', 'https://school.e-sports.or.kr/notice/view/1123'),
            ('unknown', 'https://school.e-sports.or.kr/notice/view/1123'),
            ('kespa-school', 'https://evil.school.e-sports.or.kr/notice/view/1123'),
            ('kespa-school', 'https://school.e-sports.or.kr.example.com/notice/view/1123'),
            ('kespa-school', 'http://school.e-sports.or.kr/notice/view/1123'),
            ('kespa-school', 'https://user@school.e-sports.or.kr/notice/view/1123'),
            ('kespa-school', 'https://school.e-sports.or.kr:8443/notice/view/1123'),
        ):
            with self.subTest(url=url, publisher=publisher), self.assertRaises(ValueError):
                require_authority({'evidence': [{'publisher_id': publisher, 'url': url}]})

    def test_existing_education_authority_is_retained(self):
        require_authority({'evidence': [{'publisher_id': 'busan', 'url': 'https://home.pen.go.kr/bssc/'}]})


if __name__ == '__main__':
    unittest.main()
