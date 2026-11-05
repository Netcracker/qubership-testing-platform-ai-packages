import java.io.File;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.stream.StreamSource;
import javax.xml.validation.Schema;
import javax.xml.validation.SchemaFactory;
import javax.xml.validation.Validator;
import org.w3c.dom.Document;
import org.xml.sax.ErrorHandler;
import org.xml.sax.SAXParseException;

/**
 * Validates Diameter dictionaries against their XSD files.
 *
 * <p>Usage: {@code java ValidateDictionaries.java DICTIONARY_DIR}. The schemas are read from
 * {@code DICTIONARY_DIR/xsd}. A file whose root element is {@code dictionary} is checked against
 * diameter-dictionary.xsd, and one whose root element is {@code diameter-command-dictionary}
 * against diameter-command.xsd. Errors are grouped by message, with the line of the first
 * occurrence. The exit status is 1 if any file is invalid.
 */
public class ValidateDictionaries {

  private static final int MAX_MESSAGE_LENGTH = 230;

  /** Collects validation errors, counting each distinct message. */
  private static final class Collector implements ErrorHandler {

    /** Message to {count, line of the first occurrence}. */
    private final Map<String, int[]> messages = new LinkedHashMap<>();

    private void record(SAXParseException e) {
      int[] entry = messages.computeIfAbsent(e.getMessage(), k -> new int[] {0, e.getLineNumber()});
      entry[0]++;
    }

    @Override
    public void warning(SAXParseException e) {
      record(e);
    }

    @Override
    public void error(SAXParseException e) {
      record(e);
    }

    @Override
    public void fatalError(SAXParseException e) throws SAXParseException {
      throw e;
    }
  }

  /** Validates one file, prints the result, and returns the number of errors. */
  private static int validate(File file, Schema dictionarySchema, Schema commandSchema)
      throws Exception {
    DocumentBuilderFactory builderFactory = DocumentBuilderFactory.newInstance();
    builderFactory.setNamespaceAware(true);
    builderFactory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
    Document document = builderFactory.newDocumentBuilder().parse(file);
    String root = document.getDocumentElement().getLocalName();
    Schema schema = "dictionary".equals(root) ? dictionarySchema : commandSchema;

    Collector collector = new Collector();
    Validator validator = schema.newValidator();
    validator.setErrorHandler(collector);
    try {
      validator.validate(new StreamSource(file));
    } catch (SAXParseException e) {
      collector.messages.put("FATAL " + e.getMessage(), new int[] {1, e.getLineNumber()});
    }

    int total = collector.messages.values().stream().mapToInt(v -> v[0]).sum();
    String verdict = total == 0 ? "valid" : total + " errors";
    System.out.printf("%s (%s): %s%n", file.getName(), root, verdict);
    for (Map.Entry<String, int[]> entry : collector.messages.entrySet()) {
      String message = entry.getKey();
      if (message.length() > MAX_MESSAGE_LENGTH) {
        message = message.substring(0, MAX_MESSAGE_LENGTH) + "...";
      }
      int[] where = entry.getValue();
      System.out.printf("    x%d, first at line %d: %s%n", where[0], where[1], message);
    }
    return total;
  }

  public static void main(String[] args) throws Exception {
    if (args.length != 1) {
      System.err.println("Usage: java ValidateDictionaries.java DICTIONARY_DIR");
      System.exit(2);
    }
    File dir = new File(args[0]);
    SchemaFactory factory = SchemaFactory.newInstance(XMLConstants.W3C_XML_SCHEMA_NS_URI);
    factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
    Schema dictionarySchema = factory.newSchema(new File(dir, "xsd/diameter-dictionary.xsd"));
    Schema commandSchema = factory.newSchema(new File(dir, "xsd/diameter-command.xsd"));

    File[] files = dir.listFiles((d, name) -> name.endsWith(".xml"));
    if (files == null || files.length == 0) {
      System.err.println("No .xml files in " + dir);
      System.exit(2);
    }
    Arrays.sort(files);
    int invalid = 0;
    for (File file : files) {
      if (validate(file, dictionarySchema, commandSchema) > 0) {
        invalid++;
      }
    }
    System.out.printf("%d of %d files are invalid%n", invalid, files.length);
    System.exit(invalid == 0 ? 0 : 1);
  }
}
