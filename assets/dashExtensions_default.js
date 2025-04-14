window.dashExtensions = Object.assign({}, window.dashExtensions, {
    default: {
        function0: function(feature, context) {
            const {
                classes,
                colorscale,
                style,
                colorProp
            } = context.hideout;
            const value = feature.properties[colorProp];
            for (let i = classes.length - 1; i >= 0; --i) {
                if (value >= classes[i]) {
                    style.fillColor = colorscale[i];
                    break;
                }
            }
            style.fillOpacity = 0.4; // Augmenter la transparence
            return style;
        },
        function1: function(feature, layer, context) {
            layer.bindTooltip(`This is <b> html </b>. Foo is [${feature.properties.siret}])`)
            layer.bindTooltip(`<b>Etablissement similaire : </b><br><b>Raison sociale : </b>[${feature.properties.nom_complet}]<br><b>SIRET : </b>[${feature.properties.siret}]<br><b>Activite principale : </b>[${feature.properties.activite_principale}]`)
        }
    }
});