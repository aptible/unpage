if (window.location.hostname.indexOf("localhost") == -1) {
  !function (key) {
    if (window.reb2b) return;
    window.reb2b = { loaded: true };
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://b2bjsstore.s3.us-west-2.amazonaws.com/b/" + key + "/" + key + ".js.gz";
    document.getElementsByTagName("script")[0].parentNode.insertBefore(s, document.getElementsByTagName("script")[0]);
  }("Q1N5W0HZG3O5");
}
