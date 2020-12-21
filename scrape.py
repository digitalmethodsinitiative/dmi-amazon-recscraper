from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import JavascriptException, TimeoutException

import re
import itertools
import argparse


def stealthify_browser(browser):
    """
    Stealth scripts to hide that we're headless
    From https://github.com/MeiK2333/pyppeteer_stealth
    :param browser:  Selenium browser to stealthify
    """
    browser.execute_script(open("stealthify.js").read())


def get_recommendations(url, browser):
    """
    Get Amazon recommendations for a given URL

    See carousels.js for the actual scraping code. Note that the given seed
    URLs are expected to be product page URLs; behaviour when they point to
    another type of page is undefined.

    :param str url:  Amazon item page URL to scrape
    :param browser:  Selenium WebDriver instance to scrape with
    :return dict:  A dictionary, with an item for each found recommendation
    list, that item being a dictionary with two items, "sponsored" (a boolean)
    and "items" (a list of items in that list)
    """
    stealthify_browser(browser)

    try:
        browser.get(url)
        carousel_scrape = open("carousels.js").read()
        recommendations = browser.execute_script("return %s" % carousel_scrape)
        return recommendations
    except JavascriptException as e:
        print("Javascript error: %s" % e)
        return {}
    except TimeoutException as e:
        print("Timeout while scraping, returning empty result set")
        return {}


def gdf_escape(string):
    """
    Escape string for use in GDF file

    :param str string: String to escape
    :return str:  Escaped string, wrapped in quotes
    """
    if not string:
        return '""'

    return '"' + string.replace('"', '\"') + '"'


def generate_recommendation_network(seeds, depth=0, prefix=""):
    """
    Generate GDF files for the recommendations for the seed URLs

    Scrapes recommendations for a given list of Amazon product page URLs and
    stores the scraped values as Gephi-compatible GDF files, one per type of
    recommendation (e.g. 'customers also viewed', 'customers also bought', and
    so on).

    If a depth greater than 0 is used, items are scraped breadth-first, i.e.
    first depth 0 will be scraped, then depth 1, and so on. This balloons
    extremely quickly so be very careful at depths greater than 0.

    :todo: determine how (and if) to weigh nodes and edges

    :param list seeds: A list of Amazon product page URLs to scrape
    :param int depth:  Depth for the scrape, defaults to 0. If the depth is 1,
    all recommendations found in the first iteration will also be scraped, and
    :param str prefix:  File prefix
    so on. Careful!
    """
    items = {}
    links = {}

    # set up selenium-driven browser
    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 11.1; rv:84.0) Gecko/20100101 Firefox/84.0"
    profile = webdriver.FirefoxProfile()
    profile.set_preference("general.useragent.override", user_agent)
    options = Options()
    options.add_argument("--headless")
    browser = webdriver.Firefox(firefox_profile=profile, options=options)

    # these are kind of arbitrary, but seem to work
    browser.set_page_load_timeout(15)
    browser.set_script_timeout(90)
    browser.implicitly_wait(5)

    seed_asins = set()
    current_depth = 0
    initial_asins = None

    while current_depth <= depth:
        # we use ASINs as unique identifiers - they can be found at a
        # predictable place in the product page URL
        seed_asins |= set([seed.split("/dp/")[1].split("/")[0] for seed in seeds])
        if not initial_asins:
            initial_asins = seed_asins

        # this will store ASINs for a next round of scraping, if we end up
        # doing one
        new_seeds = []

        progress = 1
        for seed in seeds:
            # give recommendation URLs (which are relative) the same host as
            # the seed URL
            amazon_host = "/".join(seed.split("/")[:3])
            print("Scraping %s... (depth %i, %i/%i)" % (seed, current_depth, progress, len(seeds)))
            progress += 1

            # get the actual recommendations - this will typically take a while
            recommendations = get_recommendations(seed, browser)
            seed_asin = seed.split("/dp/")[1].split("/")[0]

            # process recommendations
            for list_title, list_items in recommendations.items():
                if list_title not in links:
                    links[list_title] = set()

                for item in list_items["items"]:
                    metadata = item.copy()
                    if metadata["link"][0:4] != "http":
                        metadata["link"] = amazon_host + metadata["link"]

                    # not sure what to do with this...
                    del metadata["rank"]

                    asin = item["asin"]
                    if asin not in items:
                        items[asin] = metadata

                    # if the item has not been scraped earlier, it is a
                    # candidate for scraping in a next iteration. Note that
                    # this does not account for different amazon domains - but
                    # mixing them would be unadvisible anyway
                    if asin not in seed_asins:
                        new_seeds.append(metadata["link"])

                    # store the pair as a simple a-b string. using a hashable
                    # type here (i.e. a string) allows using a set to store
                    # them, which automatically elimiates duplicates
                    pair = "-".join([seed_asin, asin])
                    links[list_title].add(pair)

        # the new seeds are the old seeds - prepare for next iteration (if
        # needed)
        seeds = new_seeds
        current_depth += 1

    browser.close()

    # write GDF file
    for list_title, list_pairs in links.items():
        # only include items that actually appear in this list
        asins = set().union(*itertools.chain([pair.split("-") for pair in list_pairs]))

        filename = list_title.replace(" ", "-") + ".gdf"
        if prefix:
            filename = prefix + "-" + filename

        with open(filename, "w") as output:
            output.write(
                "nodedef>id VARCHAR, name VARCHAR,author VARCHAR,url VARCHAR,price VARCHAR,thumbnail VARCHAR,is_seed BOOLEAN\n")
            for asin, item in items.items():
                if asin not in asins:
                    continue
                is_seed = "true" if asin in initial_asins else "false"
                output.write("%s,%s,%s,%s,%s,%s,%s\n" % (
                    gdf_escape(asin), gdf_escape(item["label"]), gdf_escape(item["author"]), gdf_escape(item["link"]), gdf_escape(item["price"]),
                    gdf_escape(item["thumbnail"]), is_seed))

            output.write("edgedef>from VARCHAR,to VARCHAR,directed BOOLEAN\n")
            for pair in list_pairs:
                pair = pair.split("-")
                output.write("%s,%s,true\n" % tuple(pair))

if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("-i", "--input", help="File with product page URLs to scrape, one per line", required=True)
    cli.add_argument("-d", "--depth", default=0, help="Crawl depth, default 0")
    cli.add_argument("-p", "--prefix", default="", help="File name prefix for the output GDF files")
    args = cli.parse_args()

    seeds = open(args.input).readlines()
    generate_recommendation_network(seeds, int(args.depth), args.prefix)
