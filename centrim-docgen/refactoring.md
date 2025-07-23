
---

## Commit: b64996c2

**Author:** abhay  
**Date:** 2025-07-23T14:15:39+05:30  
**Message:** feat: removed custom prompt

To generate Centrim DocGen's documentation in a specific style, follow these steps:

1. Start by selecting the desired format (e.g., API Reference or User Guide) for your documentation.
2. Check if Centrim DocGen supports any other formats. If not, create a custom content type for your documentation and generate it accordingly.
3. Configure Centrim DocGen's settings to reflect the selected format. This includes setting up the title, section headings, and subheadings, among others.
4. Generate the documentation according to the selected format. This involves copying and pasting the content to the desired format, such as HTML, Markdown or PDF.
5. Review the generated documentation for readability, coherence, and accuracy. Use tools like Evernote or Google Sheets to keep track of your notes on each page and ensure a cohesive structure.
6. Once you're satisfied with the generated documentation, publish it on your website or online documentation repository.
7. Follow Centrim DocGen's recommended best practices for authoring and publishing documentation. This includes optimizing the content for search engines, using headings appropriately, and ensuring that all necessary information is provided.

---

---

## Commit: b64996c2

**Author:** abhay  
**Date:** 2025-07-23T14:15:39+05:30  
**Message:** feat: removed custom prompt

This is an updated version of the project with new instructions and a detailed explanation on how to generate the required documentation. The steps outlined below are based on the latest version of the code, which includes updated documentation comments and improved structure for better readability.

Step 1: Set up your development environment
- Install Node.js (version 16.x) with NPM. You can download it from https://nodejs.org/en/download/
- Clone this repository to your local machine by running the following command in the terminal or command prompt:
```
$ git clone https://github.com/nickwang93/centrimDocGen.git
```

Step 2: Install dependencies
- Open a new terminal or Command Prompt window and navigate to the directory where you cloned the repository.
- Run the following command to install all dependencies needed for this project:
```
$ npm install
```

Step 3: Start the development server
- Start the development server by running the following command in the terminal or Command Prompt window:
```
$ npm run start
```
This will automatically open a new browser tab with the development server running at http://localhost:1234/

Step 4: Build the documentation
To build the documentation, you need to create a markdown file called "readme.md" in the root of the repository. This file should contain all the necessary information about the project, including its purpose, how to use it, and its dependencies. You can then run the following command in the terminal or Command Prompt window:
```
$ npx docusaurus build
```
This command will build the documentation into a single HTML file called "docusaurus.html" in the root of the repository.

Step 5: Test your documentation
Once the documentation is built, you can test it by opening the "docusaurus.html" file in your web browser. You should see the main page with all the necessary information and links to the project's other pages.

Step 6: Add comments to code snippets
To provide better readability for users of this documentation, please add inline comments to code snippets to explain their purpose. These comments will appear as vertical text underneath the code snippet in your documentation.

Step 7: Update the project's repository structure and add new sections
- Open a new terminal or Command Prompt window and navigate to the directory where you cloned the repository.
- Run the following command to update the project's repository structure:
```
$ git pull origin master
```
This will pull the latest changes from the main branch of this repository.

- Create a new section for each feature or functionality of your project by creating a new markdown file in the "docs" directory and adding it to the sidebar menu (or wherever else you want to add it). You can then add comments to explain the purpose of each section.

Step 8: Add new features and update documentation accordingly
If you have added new features or functionality to your project, please ensure that you also update the corresponding sections in the documentation as necessary. These updates should appear as inline comments next to the relevant code snippets and should include details on how to use these features.

Step 9: Update project dependencies
- Open a new terminal or Command Prompt window and navigate to the directory where you cloned the repository.
- Run the following command to update project dependencies:
```
$ npm install
```
This will automatically install all dependencies needed for this project, including any updates that were made during the development process.

Step 10: Deploy the documentation
Once your documentation has been built and updated, you can deploy it to a web hosting platform like GitHub Pages or Netlify. To do this, run the following command in the terminal or Command Prompt window:
```
$ npm run start
```
This will automatically build your project and deploy it to the specified host/platform. You should see a message indicating that the documentation has been successfully deployed.

Step 11: Test on different platforms and devices
Once you have tested your documentation on all major web browsers, mobile devices, and tablets, feel free to run the following command in the terminal or Command Prompt window:
```
$ npm run test
```
This will launch a full test suite that simulates various user scenarios (e.g., typing text, navigating through the documentation, etc.) on multiple platforms and devices.

That's it! Your new documentation is now ready to be viewed on your preferred web browser or in your chosen platform.

---
