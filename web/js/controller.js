
var DBLPApp = angular.module('DBLPApp', []);

DBLPApp.controller('DBLPCtrl', function ($scope, $http) {
    $scope.who = "";
    $scope.url = "";
    $scope.searchResults = [];
    $scope.searchStatus = 200;
    $scope.collaborators = {};
    $scope.collaboratorsStatus = 200;
    $scope.mapWidth = 0;
    $scope.mapHeight = 0;
    $scope.accumulate = false;
    $scope.search = function() {
        $http.get("search/" + encodeURIComponent($scope.who), {})
            .then(function success(response) {
                $scope.searchResults = response.data;
                $scope.searchStatus = response.status;
            }, function error(response) {
                console.log(response);
                $scope.searchStatus = response.status;
            });
    }
    $scope.setURL = function(url) {
        $scope.url = url;
    }
    $scope.getCollaborators = function() {
        $http.get("collaborators/" + encodeURIComponent($scope.url), {})
            .then(function success(response) {
                if (!$scope.accumulate) $scope.collaborators = {}
                $scope.collaboratorsStatus = response.status;
                for (var i=0; i<response.data.length; i++) {
                    $scope.collaborators[response.data[i].url] = response.data[i];
                    $scope.collaborators[response.data[i].url].loading = true;
                    $http.get("geolocate/" + encodeURIComponent(response.data[i].url), {})
                        .then(function success(response) {
                            $scope.collaborators[response.data.url].loading = false;
                            if ("coords" in response.data)
                                $scope.collaborators[response.data.url].coords = response.data.coords;
                        }, function error(response) {
                            console.log(response);
                        });
                }
            }, function error(response) {
                console.log(response);
                $scope.collaboratorsStatus = response.status;
            });
    }
    $scope.plotMap = function() {
        var locations = []
        for (var p in $scope.collaborators) {
            var coords = $scope.collaborators[p].coords;
            if (coords == undefined) continue;
            if (!Array.isArray(coords))
                coords = coords.split(',').map(Number);
            locations.push([$scope.collaborators[p].name, coords[0], coords[1]]);
        }
        var bounds = new google.maps.LatLngBounds();
        for (var i = 0; i < locations.length; i++) { 
	        bounds.extend(new google.maps.LatLng(locations[i][1], locations[i][2]));
        }
        var map = new google.maps.Map(document.getElementById('map'), {
          center: bounds.getCenter(),
          mapTypeId: google.maps.MapTypeId.ROADMAP
        });
        map.fitBounds(bounds);
        var infowindow = new google.maps.InfoWindow();
        var markers = locations.map(function(location) { 
          return new google.maps.Marker({
            position: new google.maps.LatLng(location[1]+0.1*Math.random()-0.05, location[2]+0.1*Math.random()-0.05),
            map: map,
            label: {
                text: location[0],
                color: '#eb3a44',
                fontSize: "16px",
                fontWeight: "bold",
            }
          });
        });
        var markerCluster = new MarkerClusterer(map, markers,
                            {imagePath: 'https://developers.google.com/maps/documentation/javascript/examples/markerclusterer/m', gridSize: 30});
        $scope.mapWidth = document.getElementById('map').parentNode.offsetWidth;
        $scope.mapHeight = $scope.mapWidth*3/4;
    }
});
