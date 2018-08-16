/* -*- mode: espresso; espresso-indent-level: 2; indent-tabs-mode: nil -*- */
/* vim: set softtabstop=2 shiftwidth=2 tabstop=2 expandtab: */

/**
 * request.js
 *
 * requirements:
 *	 tools.js
 *
 */

/**
 * Implements a cross browser HTTPrequest-FIFO-queue.
 */
var RequestQueue = function(originUrl, csrfToken)
{
  var self = this;
  var queue = [];		//!< queue of waiting requests
  var xmlHttp = new XMLHttpRequest();
  var spinner = null;
  // Extra headers are stored as key value pairs in an object
  var extraHeaders = {};

  var showSpinner = function()
  {
    if ( !spinner )
      spinner = document.getElementById( "spinner" );
    if ( spinner )
      spinner.style.display = "block";
  };

  var hideSpinner = function()
  {
    if ( !spinner )
      spinner = document.getElementById( "spinner" );
    if ( spinner )
      spinner.style.display = "none";
  };

  /**
   * Test whether a request is for the same host as the origin URL configured
   * for this request queue. Because this URL is configured and CATMAID
   * should always generate URLs the same way (i.e., we do not care about
   * matches with additional protocols, etc.), this is a simple test. For
   * more robust matching, see:
   * https://docs.djangoproject.com/en/1.6/ref/contrib/csrf/
   */
  var sameOrigin = function (url) {
    return 0 === url.indexOf(originUrl);
  };

  var send = function()
  {
    showSpinner();
    var item = queue[0];
    xmlHttp.open(
      item.method,
      item.request,
      true );
    // Accept all content types as response. This is needed to not have Firefox
    // add its own defaults, which in turn triggers Django Rest Framework in the
    // back-end to return a website for views it covers.
    xmlHttp.setRequestHeader( "Accept", "*/*" );
    xmlHttp.setRequestHeader( "X-Requested-With", "XMLHttpRequest");
    if ( item.method == "POST" || item.method == "PUT" )
    {
      xmlHttp.setRequestHeader( "Accept", "*/*" );
      xmlHttp.setRequestHeader( "Content-type", "application/x-www-form-urlencoded" );
      // xmlHttp.setRequestHeader( "Content-length", queue[ 0 ].data.length );
      // xmlHttp.setRequestHeader( "Connection", "close" );
    }
    xmlHttp.setRequestHeader( "X-Requested-With", "XMLHttpRequest" );
    if (!RequestQueue.csrfSafe(item.method) && sameOrigin(item.request)) {
      xmlHttp.setRequestHeader('X-CSRFToken', csrfToken);
    }

    // Allow custom response types
    xmlHttp.responseType = item.responseType ? item.responseType : "";

    // Add extra headers
    for (var headerName in extraHeaders) {
      xmlHttp.setRequestHeader(headerName, extraHeaders[headerName]);
    }
    for (var headerName in item.headers) {
      xmlHttp.setRequestHeader(headerName, item.headers[headerName]);
    }
    xmlHttp.onreadystatechange = callback;
    xmlHttp.send( item.data );
  };

  var callback = function()
  {
    if ( xmlHttp.readyState == 4 )
    {
      var advance = true;
      hideSpinner();
      try {
        // Throw exception in case of a network error
        if (xmlHttp.status === 0) {
          throw new CATMAID.NetworkAccessError("Network unreachable",
              "Please check your network connection");
        }
        var isTextResponse = (xmlHttp.responseType === '' || xmlHttp.responseType === 'text');
        var responseData = isTextResponse ? xmlHttp.responseText : xmlHttp.response;
        var responseXML = isTextResponse ? xmlHttp.responseXML : null;
        var dataSize = xmlHttp.responseType === 'arraybuffer' ?
            responseData.byteLength : responseData.length;
        var contentType = xmlHttp.getResponseHeader('Content-Type');
        queue[ 0 ].callback(xmlHttp.status, responseData, responseXML, dataSize, contentType);
      } catch(error) {
        // Call back with Service Unavailable error (503) for consistency with
        // other error cases and to give the caller information about the error.
        queue[ 0 ].callback(503, error, "");
        // In case of error, reset complete queue
        queue.length = 0;
        advance = false;
        // Re-throw error
        throw error;
      }
      if (advance) {
        // Move forward in queue
        queue.shift();
        if ( queue.length > 0 ) {
          send();
        }
      }
    }
  };

  return {
    /**
     * Returns if there is some request pending or not.
     */
    busy : function(){ return ( queue.length > 0 ); },

    /**
     * Registers a request including a callback to the queue for waiting or
     * starts it imediately.
     */
    register : function(
        r,		//!< string  request
        m,		//!< string  method	"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD" or "OPTIONS"
        d,		//!< object  data		object with key=>value
        c,		//!< function callback
        id,		//!< string  id
        responseType,
        headers
    )
    {
      switch( m )
      {
      case "POST":
      case "PUT":
        queue.push(
          {
            request : r,
            method : m,
            data : RequestQueue.encodeObject( d ),
            callback : c,
            id : id,
            responseType: responseType,
            headers: headers || {}
          }
        );
        break;
      default:
        var request = "";
        var encoded = RequestQueue.encodeObject( d );
        if (encoded !== "") {
          request = "?" + encoded;
        }
        queue.push(
          {
            request : r + request,
            method : m,
            data : null,
            callback : c,
            id : id,
            responseType: responseType,
            headers: headers || {}
          }
        );
      }
      if ( queue.length == 1 )
      {
        send();
      }
    },

    /**
     * Registers a request including a callback to the queue for waiting or
     * starts it imediately.  In case the requests id exists in the queue
     * already, the existing instance will be removed assuming that it is
     * outdated.
     */
    replace : function(
        r,		//!< string  request
        m,		//!< string  method	"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD" or "OPTIONS"
        d,		//!< object  data		object with key=>value
        c,		//!< funtion callback
        id,		//!< string  id
        responseType,
        headers
    )
    {
      var removedRequest;
      for ( var i = 1; i < queue.length; ++i )
      {
        if ( queue[ i ].id == id )
        {
          removedRequest = queue.splice( i, 1 );
          CATMAID.statusBar.replaceLast( "replacing request ", + r );
          // Send a distinguishable error reponse with the callback:
          removedRequest[0].callback(200, JSON.stringify({'error': 'REPLACED'}), null);
        }
      }
      this.register( r, m, d, c, id, responseType, headers );
    },

    /**
     * Add a header that will be added to every new request.
     */
    addHeader: function(name, value) {
      extraHeaders[name] = value;
    },

    /**
     * Remove a header that was added before.
     */
    removeHeader: function(name) {
      delete extraHeaders[name];
    }
  };
};

RequestQueue.csrfSafe = function (method) {
  // these HTTP methods do not require CSRF protection
  return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
};

RequestQueue.encodeArray = function( a, p ) {
  var q = "";
  for ( var i = 0; i < a.length; ++i )
  {
    var r = p + "[" + i + "]";

    switch ( typeof a[ i ] )
    {
    case "undefined":
      break;
    case "function":
    case "object":
      if ( a[ i ].constructor == Array && a[ i ].length > 0 )
        q += RequestQueue.encodeArray( a[ i ], r ) + "&";
      else
        q += RequestQueue.encodeObject( a[ i ], r ) + "&";
      break;
    default:
      q += r + "=" + encodeURIComponent( a[ i ] ) + "&";
      break;
    }
  }
  q = q.replace( /\&$/, "" );

  return q;
};

RequestQueue.encodeObject = function( o, p )
{
  var q = "";
  for ( var k in o )
  {
    var r;
    if ( p )
      r = p + "[" + k + "]";
    else
      r = k;

    switch ( typeof o[ k ] )
    {
    case "undefined":
      break;
    case "function":
    case "object":
      if (null === o[k]) {
        break;
      }
      if ( o[ k ].constructor == Array && o[ k ].length > 0 )
        q += RequestQueue.encodeArray( o[ k ], r ) + "&";
      else
        q += RequestQueue.encodeObject( o[ k ], r ) + "&";
      break;
    default:
      q += r + "=" + encodeURIComponent( o[ k ] ) + "&";
      break;
    }
  }
  q = q.replace( /\&$/, "" );

  return q;
};
