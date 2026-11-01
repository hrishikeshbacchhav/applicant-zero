from unittest.mock import patch
from xml.etree import ElementTree

from applicant_zero.sources.weworkremotely import CATEGORY_FEEDS, RSS_URL, _job_from_item, build_category_rss_url, fetch_jobs, fetch_targeted_jobs


def test_wwr_mapping_keeps_attributed_listing_and_worldwide_eligibility():
    item = ElementTree.fromstring("""<item><title>Example: Data Analyst</title><link>https://weworkremotely.com/remote-jobs/example</link><description><![CDATA[Work from anywhere using SQL.]]></description><pubDate>Thu, 25 Sep 2026 00:00:00 GMT</pubDate></item>""")
    job = _job_from_item(item)
    assert job.source == "We Work Remotely"
    assert job.url == "https://weworkremotely.com/remote-jobs/example"
    assert job.location == "Remote, Worldwide"
    assert "Published:" in job.description


def test_wwr_fetch_caps_public_feed_items():
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b"<rss><channel><item><title>Example: Data Analyst</title><link>https://weworkremotely.com/remote-jobs/example</link></item></channel></rss>"
    with patch("applicant_zero.sources.weworkremotely.urlopen", return_value=Response()):
        jobs = fetch_jobs(max_items=999)
    assert len(jobs) == 1
    assert RSS_URL.startswith("https://")


def test_wwr_uses_explicitly_published_category_feed_urls():
    assert build_category_rss_url("remote-customer-support-jobs") == "https://weworkremotely.com/categories/remote-customer-support-jobs.rss"
    assert len(CATEGORY_FEEDS) == 4


def test_wwr_targeted_fetch_retains_successful_category_feeds_when_one_fails():
    def reader(*, rss_url=RSS_URL, **_):
        if "management" in rss_url:
            raise OSError("temporary failure")
        return [
            _job_from_item(ElementTree.fromstring("<item><title>Example: IT Support Officer</title><link>https://weworkremotely.com/remote-jobs/example</link></item>"))
        ]

    with patch("applicant_zero.sources.weworkremotely.fetch_jobs", side_effect=reader):
        jobs, report = fetch_targeted_jobs(categories=("remote-customer-support-jobs", "remote-management-and-finance-jobs", "remote-programming-jobs"))

    assert len(jobs) == 2
    assert report.requests == 3
    assert report.errors == ("remote-management-and-finance-jobs: temporary failure",)
