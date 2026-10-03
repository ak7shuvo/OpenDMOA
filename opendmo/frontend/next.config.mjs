/** Static export: the Python backend serves ./out — end users never need Node. */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  reactStrictMode: true,
  poweredByHeader: false,
  images: { unoptimized: true },
  productionBrowserSourceMaps: false,
};
export default nextConfig;
