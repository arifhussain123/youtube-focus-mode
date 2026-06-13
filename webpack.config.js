const path = require('path');
const CopyWebpackPlugin = require('copy-webpack-plugin');

module.exports = {
  entry: {
    popup: './src/popup/index.jsx',
    content: './src/content/content.js',
    background: './src/background/background.js',
  },
  output: {
    path: path.resolve(__dirname, 'dist'),
    // Popup bundle lives next to its HTML; content script sits at dist root
    // so the manifest can reference it as "content.js".
    filename: (pathData) =>
      pathData.chunk.name === 'popup' ? 'popup/popup.js' : '[name].js',
    clean: true,
  },
  resolve: {
    extensions: ['.js', '.jsx'],
  },
  module: {
    rules: [
      {
        test: /\.jsx?$/,
        exclude: /node_modules/,
        use: 'babel-loader',
      },
      {
        // Popup styling only. content.css is NOT imported anywhere — it is
        // copied verbatim (below) and referenced by the manifest so it loads
        // as a content-script stylesheet at document_start.
        test: /\.css$/,
        use: ['style-loader', 'css-loader'],
      },
    ],
  },
  plugins: [
    new CopyWebpackPlugin({
      patterns: [
        { from: 'public/manifest.json', to: 'manifest.json' },
        { from: 'public/icons', to: 'icons' },
        { from: 'src/popup/index.html', to: 'popup/index.html' },
        { from: 'src/content/content.css', to: 'content.css' },
      ],
    }),
  ],
};
