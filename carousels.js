(async () => {
    let result = await (async () => {
        //simple sleep function that can be used in asynchronous code
        if (!window.sleep) {
            window.sleep = function (ms) {
                return new Promise(resolve => setTimeout(resolve, ms));
            }
        }

        //wait for a carousel container to have loaded the next page of results
        //will always resolve eventually, even if loading has not finished
        //empty results will be ignored in the actual scraping
        if (!window.next_carousel_page_loaded) {
            window.next_carousel_page_loaded = (element, timeout = 1000) => {
                let interval = 50;
                let max_attempts = timeout / interval;
                let attempt = 0;
                let poll = function (resolve) {
                    if (attempt >= max_attempts || (element.getAttribute('aria-busy') === 'false' && element.querySelectorAll('.a-carousel-card-empty').length === 0)) {
                        resolve(true)
                    } else {
                        attempt += 1;
                        setTimeout(function () {
                            poll(resolve)
                        }, interval);
                    }
                };
                return new Promise(poll);
            }
        }

        //get item data (the item is not in any lists)
        let own_title = document.getElementById('productTitle');
        if(!own_title) {
            return {};
        }

        let own_price = document.querySelectorAll('span.header-price')[0];
        own_price = own_price ? own_price.innerText : null;

        let own_img = document.querySelectorAll('img.frontImage')[0];
        own_img = own_img ? own_img.getAttribute('src') : null;

        let item_metadata = {
            asin: document.location.href.split(/(d|g)p/)[1].split('/')[0],
            label: own_title.innerText,
            author: null,
            rank: 0,
            link: document.location.href.split('?')[0],
            thumbnail: own_img,
            price: own_price,
            is_seed: true
        }

        //first scroll to the bottom of the page - slowly! to make sure all carousels load
        while (document.documentElement.scrollTop < document.documentElement.scrollHeight - window.innerHeight) {
            document.documentElement.scrollTop += 100;
            await sleep(50);
        }

        //init
        let carousels = document.querySelectorAll('ol.a-carousel[role=list]');
        let items = {};
        let carousel_name = null;

        for (const carousel of carousels) {
            carousel_name = null;
            let parent = carousel;
            while (!parent.classList.contains('a-carousel-container') && parent.parentNode) {
                parent = parent.parentNode;
            }

            //if this is not inside a carousel container, ignore this, we cannot
            //predict its structure
            if (!parent || !parent.classList.contains('a-carousel-container')) {
                continue;
            }

            //ignore videos carousel, it's not the type of data we are looking for
            if (parent.id.indexOf('related-videos') !== -1) {
                continue;
            }

            //the page contains some pre-loaded half-filled carousels. ignore these,
            //though they could be interesting in some situations, but the incomplete
            //nature of these makes them hard to scrape in the same way
            if (getComputedStyle(parent).getPropertyValue('display') === 'none') {
                continue;
            }

            //find carousel name - we need one to scrape the data properly
            carousel_name = parent.querySelectorAll('div.a-carousel-header-row h2')[0];
            if (!carousel_name) {
                continue;
            }

            //this is the 'items you have viewed before' carousel, which we can ignore
            if (carousel_name.innerHTML.indexOf('/gp/yourstore/pym/') !== -1) {
                continue;
            }

            carousel_name = carousel_name.innerText;
            let sponsored = carousel_name.indexOf('Sponsor') >= 0;
            let carousel_items = [item_metadata];
            let rank = 1;
            carousel_name = carousel_name.split("\n")[0];

            //carousels may have multiple pages we need to iterate through - find out how
            //many. we stop at 10 pages since, well, come on
            let page_count = parent.querySelectorAll('span.a-carousel-page-max')[0];
            page_count = page_count && !isNaN(page_count) ? parseInt(page_count.innerText) : 1;
            page_count = Math.min(page_count, 9);
            let current_page = 0;

            //now scrape items from each carousel page
            while (current_page <= page_count) {
                for (const carousel_item of carousel.querySelectorAll('li.a-carousel-card:not(.a-carousel-card-empty)')) {
                    let link = carousel_item.querySelectorAll('a.a-link-normal')[0];
                    link = link ? link.getAttribute('href').split('?')[0] : null;

                    if (!link) {
                        continue;
                    }

                    if (!link.match(/\/[dg]p\//g) || link.match(/picassoRedirect\.html/g)) {
                        //skip non-product links
                        continue;
                    }

                    let img = carousel_item.getElementsByTagName('img')[0];
                    img = img ? img.getAttribute('src') : null;

                    let label = carousel_item.querySelectorAll('div.p13n-sc-truncated')[0];
                    label = label ? (label.hasAttribute('title') ? label.getAttribute('title') : label.innerText) : null;

                    let asin = carousel_item.querySelectorAll('div.sp_offerVertical')[0];
                    asin = asin ? asin.getAttribute('data-asin') : link.split('/')[3];

                    let price = carousel_item.querySelectorAll('span.a-color-price')[0];
                    price = price ? price.innerText : null;

                    /*let review_num = carousel_item.querySelectorAll('div.a-icon-row .a-size-small')[0];
                    review_num = review_num ? review_num.innerText : null;

                    let review_score = carousel_item.querySelectorAll('div.a-icon-row .a-size-small')[0];
                    review_score = review_score ? review_score.parentNode.querySelectorAll('a')[0].getAttribute('title').split(' ')[0] : null;*/

                    let author = carousel_item.querySelectorAll('span.a-truncate-cut')[0];
                    author = author ? author.innerText : null;

                    let rows = carousel_item.querySelectorAll('div.a-row.a-size-small');
                    if (author + '' === '' && rows.length > 0) {
                        author = rows[0].innerText;
                    }

                    let item_data = {
                        rank: rank,
                        link: link,
                        asin: asin,
                        thumbnail: img,
                        label: label,
                        author: author,
                        price: price,
                        //review_num: review_num,
                        //review_score: review_score
                    };
                    rank += 1;
                    carousel_items.push(item_data)

                    if(carousel_items.length > window.max_carousel_items) {
                        break;
                    }
                }

                current_page += 1;
                if (current_page < page_count && carousel_items.length < window.max_carousel_items) {
                    let button = parent.querySelectorAll('.a-carousel-goto-nextpage')[0];
                    if (!button) {
                        break;
                    }

                    //simulate clicking the 'next page' button for this carousel
                    let clickEvent = document.createEvent('HTMLEvents');
                    clickEvent.initEvent('click', true, false);
                    button.dispatchEvent(clickEvent);

                    //wait for the next page to load, or for 5 seconds to pass
                    //250 buffer around this for attributes to update and items to render
                    await sleep(250);
                    await next_carousel_page_loaded(carousel, 'aria-busy', 'false', 5000);
                    await sleep(250);
                }

            }
            if (carousel_name) {
                items[carousel_name] = {
                    items: carousel_items,
                    sponsored: sponsored
                };
            }
        }
        return items;
    })();
    console.log(result);
    return result;
})();
