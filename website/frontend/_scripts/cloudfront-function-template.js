var redirects = @REDIRECTS@;

function handler(event) {
    var request = event.request;
    var uri = request.uri;
    var should_redirect = false;

    // If the user went to an alias, redirect to www.avmapper.com
    if (request.headers.host.value != 'www.avmapper.com') {
        should_redirect = true;
    }

    // Check to see if this is one of the explicit redirects
    if (uri in redirects) {
        uri = redirects[uri];
        should_redirect = true;
    }

    // Check to see if the destination is a directory. If so, redirect to something
    // with a trailing slash
    if (!uri.includes('.') && !uri.endsWith('/')) {
        uri += '/';
        should_redirect = true;
    }

    // Redirect if needed
    if (should_redirect) {
        return {
           statusCode: 301,
           statusDescription: 'Permanently Moved',
           headers: {
             'location': { 'value': 'https://www.avmapper.com' + uri }
           }
        };
    }

    // If this is a directory, don't redirect, but retrieve index.html from that
    // directory
    if (uri.endsWith('/')) {
        request.uri += 'index.html';
    }

    return request;
}
