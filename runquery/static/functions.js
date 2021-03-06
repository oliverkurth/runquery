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

