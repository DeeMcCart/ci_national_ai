// Define an async function to fetch and use the environment variables
async function fetchAndUseEnvVars() {
  try {
      // Fetch environment variables from an API endpoint
      const response = await fetch('/api/env', {
          method: 'GET',
          headers: {
              'Accept': 'application/json',
              'Content-Type': 'application/json'
          }
      });
      
      // Check if the response is ok (status code in the range 200-299)
      if (!response.ok) {
          throw new Error('Network response was not ok');
      }
      
      // Parse the JSON data from the response
      const data = await response.json();
      const mapboxToken = data.MAPBOX_TOKEN;

      // Log the Mapbox token
      console.log('MAPBOX_TOKEN:', mapboxToken);

      return mapboxToken;
  } catch (error) {
      // Handle errors
      console.error('Error fetching environment variables:', error);
  }
}

// Initialize map after fetching the token
async function initializeMap() {
  const mapboxToken = await fetchAndUseEnvVars();
  
  if (mapboxToken) {
    mapboxgl.accessToken = mapboxToken;

    // Initialize a map with the center being a view of Ireland
    const map = new mapboxgl.Map({
      container: "map",
      style: "mapbox://styles/mapbox/streets-v11",
      center: [-7.9333, 53.4],
      zoom: 8,
    }); // map variable

    // Search field for choosing a location for the map to go to (i.e. geocoder)
    const geocoder = new MapboxGeocoder({
      accessToken: mapboxgl.accessToken,
      mapboxgl: mapboxgl,
      types:
        "country,region,place,postcode,locality,neighborhood,address,poi,poi.landmark",
    });

    // Add the control to form.
    document.getElementById("geocoder").appendChild(geocoder.onAdd(map));

    // Add full screen control
    map.addControl(new mapboxgl.FullscreenControl());

    // Create geoJSON feature collection variables
    let placeholder = turf.featureCollection([]);
    let markers = turf.featureCollection([]);
    let clickRoute = [];

    // If location searched update map center
    geocoder.on("result", (e) => {
      hackathon.user_info.location = e.result.place_name;
      map.setCenter(e.result.center);
    });

    map.on("load", function () {
      // Add an image to use as a custom marker
      map.loadImage("assets/images/location.png", (error, image) => {
        if (error) throw error;
        map.addImage("custom-marker", image);

        // Layer for starting point
        map.addLayer({
          id: "starting-point",
          type: "symbol",
          source: {
            data: placeholder,
            type: "geojson",
          },
          layout: {
            "icon-image": "custom-marker",
          },
        });

        // Layer for markers
        map.addLayer({
          id: "route-points",
          type: "symbol",
          source: {
            data: markers,
            type: "geojson",
          },
          layout: {
            "icon-allow-overlap": false,
            "icon-ignore-placement": true,
            "icon-image": "marker-15",
          },
        });
      });
    });

    function errorCurrentLocation() {
      alert(
        "Couldn't find your current location",
        "warning",
        "noCurrentLocationAlert"
      );
    }

    function createStartMarker(start) {
      map
        .getSource("starting-point")
        .setData(turf.featureCollection([turf.point(start)]));
    }

    function updateRoute(click) {
      clickRoute.push(click);
      document.getElementById("way-points").innerHTML = clickRoute.length;
    }

    function setStartMarker(click) {
      if (click.coords == undefined) {
        createStartMarker(click);
      } else {
        let start = [
          parseFloat(click.coords.longitude.toFixed(6)),
          parseFloat(click.coords.latitude.toFixed(6)),
        ];
        updateRoute(start);
        createStartMarker(start);
        map.setCenter(start);
      }
    }

    function addMarker(markers) {
      map.getSource("route-points").setData(markers);
    }
  } else {
    console.error('Failed to retrieve Mapbox token');
  }
}

// Call the function to initialize the map
initializeMap();
