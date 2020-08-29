aira.agrifieldEditDocumentReady = () => {
  document.getElementById('id_use_custom_parameters').onclick = () => {
    const customPar = document.getElementById('custom_par');
    customPar.style.display = (
      customPar.style.display === 'none' ? 'block' : 'none'
    );
  };

  /* The following should be set directly in the HTML, with the "step"
     * attribute. However, we are generating this through django-bootstrap3's
     * {% bootstrap_field %}; it isn't clear if and how this can be configured.
     */
  document.getElementById('id_custom_efficiency').step = 0.05;
  document.getElementById('id_custom_irrigation_optimizer').step = 0.01;
  document.getElementById('id_custom_root_depth_max').step = 0.1;
  document.getElementById('id_custom_root_depth_min').step = 0.1;
  document.getElementById('id_custom_max_allowed_depletion').step = 0.01;
  document.getElementById('id_custom_field_capacity').step = 0.01;
  document.getElementById('id_custom_wilting_point').step = 0.01;
  document.getElementById('id_custom_thetaS').step = 0.01;
};

aira.setupDateTimePickerForAppliedIrrigation = () => {
  $('#id_timestamp').datetimepicker({
    format: 'yyyy-mm-dd hh:ii',
    autoclose: true,
    todayBtn: true,
    pickerPosition: 'bottom-left',
  });
};

aira.map = {
  create() {
    this.leafletMap = L.map('map');
    this.getBaseLayers();
    this.showDefaultBaseLayer();
    this.addMapControls();
    this.centerMap();
  },

  getBaseLayers() {
    this.baseLayers = {
      'Open Cycle Map': this.getOpenCycleMapBaseLayer(),
      'Hellenic Cadastre': this.getHellenicCadastreBaseLayer(),
      'Google Satellite': this.getGoogleSatelliteBaseLayer(),
    };
  },

  showDefaultBaseLayer() {
    this.baseLayers[aira.defaultBaseLayer].addTo(this.leafletMap);
  },

  addMapControls() {
    L.control.scale().addTo(this.leafletMap);
    L.control.layers(this.baseLayers).addTo(this.leafletMap);
  },

  centerMap() {
    const [lambda, phi] = aira.mapDefaultCenter;
    this.leafletMap.setView([phi, lambda], aira.mapDefaultZoom);
  },

  getOpenCycleMapBaseLayer() {
    return L.tileLayer(
      `https://{s}.tile.thunderforest.com/cycle/{z}/{x}/{y}.png?${aira.thunderforestApiKeyQueryElement}`,
      {
        attribution: (
          'Map data © <a href="https://www.openstreetmap.org/">'
          + 'OpenStreetMap</a> contributors, '
          + '<a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>'
        ),
        maxZoom: 18,
      },
    );
  },

  getHellenicCadastreBaseLayer() {
    return L.tileLayer.wms('//gis.ktimanet.gr/wms/wmsopen/wmsserver.aspx');
  },

  getGoogleSatelliteBaseLayer() {
    return L.gridLayer.googleMutant({ type: 'satellite' });
  },

  addCoveredAreaLayer(kmlUrl) {
    new L.KML(kmlUrl).addTo(this.leafletMap);
  },
};

aira.agrifieldsMap = Object.create(aira.map);
Object.assign(aira.agrifieldsMap, {
  addAgrifields(agrifields, layerName) {
    this.agrifields = agrifields;
    this.layerName = layerName;
    this.addAgrifieldsLayer();
    this.centerMapIfOnlyOneField();
  },

  addAgrifieldsLayer() {
    this.markers = [];
    this.agrifields.forEach((item) => {
      const [lng, lat] = item.coords;
      const marker = this.addMarker([lat, lng]);
      marker.bindPopup(`<a href="${item.url}">${item.name}</a>`);
    });
  },

  addMarker(latlng) {
    const marker = L.marker(latlng);
    marker.addTo(this.leafletMap);
    this.markers.push(marker);
    return marker;
  },

  centerMapIfOnlyOneField() {
    if (this.agrifields.length === 1) {
      const [lng, lat] = this.agrifields[0].coords;
      this.leafletMap.setView([lat, lng], 18);
    }
  },

});

aira.agrifieldEditMap = Object.create(aira.agrifieldsMap);
Object.assign(aira.agrifieldEditMap, {
  registerClickEvent() {
    this.leafletMap.on('click', this.moveAgrifield, this.leafletMap);
  },

  moveAgrifield(e) {
    aira.agrifieldEditMap.removeAllMarkers();
    aira.agrifieldEditMap.addMarker(e.latlng);
    document.getElementById('id_location_1').value = e.latlng.lat.toFixed(5);
    document.getElementById('id_location_0').value = e.latlng.lng.toFixed(5);
  },

  removeAllMarkers() {
    this.markers.forEach((marker) => marker.removeFrom(this.leafletMap));
    this.markers = [];
  },
});

aira.meteoMapPanel = {
  get timestepToggle() { return document.getElementById('timestep-toggle'); },
  get dateSelector() { return document.getElementById('date-input'); },
  get activeTimestep() { return this.timestepToggle.getAttribute('current-timestep'); },
  get otherTimestep() { return this.activeTimestep === 'daily' ? 'monthly' : 'daily'; },
  get dateFormat() { return this.activeTimestep === 'daily' ? 'YYYY-MM-DD' : 'YYYY-MM'; },
  get activeDate() { return this.dateSelector.value; },
  get mapserverSubdir() { return this.activeTimestep === 'daily' ? 'historical/' : 'historical/monthly'; },
  get mapserverUrl() {
    let result = aira.mapserverBaseUrl + this.mapserverSubdir;
    if (this.activeTimestep === 'daily') result += `${this.activeDate}/`;
    return result;
  },
  get meteoVarElement() { return document.getElementById(this.activeTimestep === 'daily' ? 'dailyMeteoVar' : 'monthlyMeteoVar'); },
  get layersToRequest() { return this.meteoVarElement.value + this.activeDate; },
  get activeDateIndicator() { return document.getElementById('current-date'); },

  capitalize(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
  },

  toggleBetweenMonthlyAndDaily() {
    this.timestepToggle.setAttribute('current-timestep', this.otherTimestep);
    this.setTimestep();
  },

  setTimestep() {
    document.getElementById(`raster-selector-${this.activeTimestep}`).style.display = 'block';
    document.getElementById(`raster-selector-${this.otherTimestep}`).style.display = 'none';
    this.timestepToggle.textContent = aira.timestepMessages[`switchTo${this.capitalize(this.otherTimestep)}`];
    this.setDateSelectorInitialValue();
    this.setupDateTimePicker();
    this.setupDateChangingButtons(aira.end_date);
    this.setMapDate(aira.end_date);
  },

  setDateSelectorInitialValue() {
    this.dateSelector.value = this.activeTimestep === 'daily'
      ? aira.end_date : aira.end_date.slice(0, 7);
  },

  setupDateTimePicker() {
    $('#date-input').datetimepicker('remove');
    $('#date-input').datetimepicker({
      startDate: aira.start_date,
      initialDate: aira.end_date,
      endDate: aira.end_date,
      autoclose: true,
      pickerPosition: 'bottom-left',
      format: this.dateFormat.toLowerCase(),
      minView: this.activeTimestep === 'daily' ? 'month' : 'year',
      startView: this.activeTimestep === 'daily' ? 'month' : 'year',
    });
  },

  removeCurrentMeteoLayer() {
    if (this.currentMeteoLayer) {
      aira.map.leafletMap.removeLayer(this.currentMeteoLayer);
      this.currentMeteoLayer = null;
    }
  },

  updateMeteoLayer() {
    this.removeCurrentMeteoLayer();
    this.currentMeteoLayer = L.tileLayer.wms(this.mapserverUrl, {
      layers: this.layersToRequest,
      format: 'image/png',
      transparent: true,
      opacity: 0.65,
    });
    this.currentMeteoLayer.addTo(aira.map.leafletMap);
  },

  showPopup(e) {
    const url = aira.meteoMapPanel.getFeatureInfoUrl(e.latlng);
    const xhr = new XMLHttpRequest();
    xhr.onload = () => {
      /* The test "length < 250" below is an ugly hack for not showing
       * popups at a masked area. The masked area has the value nodata,
       * which displays as a large negative number with very many digits.
       */
      if (xhr.readyState === 4 && xhr.responseText.length < 250) {
        L.popup({ maxWidth: 800 })
          .setLatLng(e.latlng)
          .setContent(xhr.responseText)
          .openOn(aira.map.leafletMap);
      }
    };

    // Make request
    xhr.open('GET', url, false);
    xhr.send();
  },

  getFeatureInfoUrl(latlng) {
    // Create a small bbox such that the point is at the bottom left of the box
    const xlow = latlng.lng;
    const xhigh = latlng.lng + 0.00001;
    const ylow = latlng.lat;
    const yhigh = latlng.lat + 0.00001;
    const bbox = `${xlow},${ylow},${xhigh},${yhigh}`;

    // Determine layers
    const vars = aira.meteoMapPanel.activeTimestep === 'daily'
      ? ['temperature', 'humidity', 'wind_speed', 'rain', 'evaporation', 'solar_radiation']
      : ['evaporation'];
    const prefix = aira.meteoMapPanel.activeTimestep === 'daily' ? 'Daily_' : 'Monthly_';
    const layers = vars.map((x) => `${prefix}${x}_${aira.meteoMapPanel.activeDate}`).join();

    const params = new URLSearchParams({
      SERVICE: 'WMS',
      VERSION: '1.1.1',
      REQUEST: 'GetFeatureInfo',
      SRS: 'EPSG:4326',
      info_format: 'text/html',
      BBOX: bbox,
      WIDTH: 2,
      HEIGHT: 2,
      X: 0,
      Y: 0,
      LAYERS: layers,
      QUERY_LAYERS: layers,
    });
    return `${aira.meteoMapPanel.mapserverUrl}?${params.toString()}`;
  },

  initialize() {
    aira.map.create();
    this.dateSelector.value = aira.end_date;
    this.setTimestep();
    aira.map.leafletMap.on('click', this.showPopup, aira.map.leafletMap);
  },

  setupDateChangingButtons(date) {
    this.activeDateIndicator.textContent = moment(date, this.dateFormat).format(this.dateFormat);
    this.setupPrevDateElement(date);
    this.setupNextDateElement(date);
  },

  setupPrevDateElement(date) {
    const timeUnit = this.activeTimestep === 'daily' ? 'days' : 'months';

    const prevDate = moment(date, this.dateFormat).subtract(1, timeUnit);
    const prevDateElement = document.getElementById('previous-date');
    prevDateElement.innerHTML = (
      `&nbsp;<i class='fa fa-chevron-left'></i>&nbsp;${prevDate.format(this.dateFormat)}`
    );
    prevDateElement.style.display = prevDate.isBefore(aira.start_date) ? 'none' : 'block';
    prevDateElement.setAttribute('date', prevDate.format(this.dateFormat));
  },

  setupNextDateElement(date) {
    const timeUnit = this.activeTimestep === 'daily' ? 'days' : 'months';

    const nextDate = moment(date, this.dateFormat).add(1, timeUnit);
    const nextDateElement = document.getElementById('next-date');
    nextDateElement.innerHTML = (
      `${nextDate.format(this.dateFormat)}&nbsp;<i class='fa fa-chevron-right'></i>&nbsp;`
    );
    nextDateElement.style.display = nextDate.isAfter(aira.end_date) ? 'none' : 'block';
    nextDateElement.setAttribute('date', nextDate.format(this.dateFormat));
  },

  setMapDate(targetDate) {
    this.setupDateChangingButtons(targetDate);
    this.updateMeteoLayer();
  },
};

aira.showAndHideIrrigationFieldsAccordingToType = () => {
  function getFormGroupElement(inputElement) {
    // Handles the case when an input is nested in another div inside the form group
    if (inputElement.parentElement.className.includes('form-group')) {
      return inputElement.parentElement;
    }
    return inputElement.parentElement.parentElement;
  }
  function hideFields(fields) {
    fields.forEach((field) => {
      const input = document.querySelector(`#id_${field}`);
      getFormGroupElement(input).style.display = 'none';
      input.removeAttribute('required');
    });
  }
  function showFields(fields) {
    fields.forEach((field) => {
      const input = document.querySelector(`#id_${field}`);
      getFormGroupElement(input).style.display = '';
      input.setAttribute('required', '');
    });
  }
  function onIrrigationTypeChanged() {
    const selectedType = document.querySelector('input[name="irrigation_type"]:checked').value;
    const fieldsPerType = {
      VOLUME_OF_WATER: ['supplied_water_volume'],
      DURATION_OF_IRRIGATION: ['supplied_duration', 'supplied_flow_rate'],
      FLOWMETER_READINGS: [
        'flowmeter_reading_start',
        'flowmeter_reading_end',
        'flowmeter_water_percentage',
      ],
    };
    Object.keys(fieldsPerType).forEach((type) => {
      if (type === selectedType) {
        showFields(fieldsPerType[type]);
      } else {
        hideFields(fieldsPerType[type]);
      }
    });
  }

  Array.from(document.querySelectorAll('input[name="irrigation_type"]'))
    .forEach((input) => input.addEventListener('change', onIrrigationTypeChanged));
  onIrrigationTypeChanged(); // Called once at the start to display according to default choice
};
