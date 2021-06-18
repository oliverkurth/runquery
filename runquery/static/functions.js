function async_request(url, callback, cbdata) {
    var xmlhttp = new XMLHttpRequest();

    xmlhttp.onreadystatechange = function() {
        if (xmlhttp.readyState == 4) {
            var result = JSON.parse(xmlhttp.responseText);
            callback(xmlhttp.status, result, cbdata);
        }
    };
    xmlhttp.open("GET", url, true);
    xmlhttp.send();
}

function async_post_json(url, jsondata, callback, cbdata) {
    var xmlhttp = new XMLHttpRequest();

    xmlhttp.onreadystatechange = function() {
        if (xmlhttp.readyState == 4) {
            var result = JSON.parse(xmlhttp.responseText);
            callback(xmlhttp.status, result, cbdata);
        }
    };
    xmlhttp.open("POST", url, true);
    xmlhttp.setRequestHeader('Content-Type', 'application/json; charset=UTF-8');
    xmlhttp.send(JSON.stringify(jsondata));
}

function isIntRange(value, low, high) {
	if (! /^[0-9]*$/.test(value)) {
		return false;
	}
	vint = parseInt(value, 10);
	if (vint < low || vint > high) {
		return false;
	}
	return true;
}

function hex2(n)
{
    if (n < 16) {
        return '0' + n.toString(16);
    } else {
        return n.toString(16);
    }
}

function range2color(value, min, max) {
    green = (value - min) * 255 / (max - min);
    if (green > 255) {
        green = 255;
    }
    red = 255 - green;
    return '#' + hex2(red) + hex2(green) + '00';
}

// https://www.w3schools.com/js/js_cookies.asp
function set_cookie(cname, cvalue, exdays) {
  var d = new Date();
  d.setTime(d.getTime() + (exdays*24*60*60*1000));
  var expires = "expires="+ d.toUTCString();
  document.cookie = cname + "=" + cvalue + ";" + expires + ";path=/";
}

function get_cookie(cname) {
  var name = cname + "=";
  var decodedCookie = decodeURIComponent(document.cookie);
  var ca = decodedCookie.split(';');
  for(var i = 0; i <ca.length; i++) {
    var c = ca[i];
    while (c.charAt(0) == ' ') {
      c = c.substring(1);
    }
    if (c.indexOf(name) == 0) {
      return c.substring(name.length, c.length);
    }
  }
  return "";
}

