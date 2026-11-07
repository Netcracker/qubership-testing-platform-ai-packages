import java.io.File;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.stream.StreamSource;
import javax.xml.validation.Schema;
import javax.xml.validation.SchemaFactory;
import javax.xml.validation.Validator;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.xml.sax.ErrorHandler;
import org.xml.sax.SAXParseException;

/**
 * Validates Diameter dictionaries against their XSD files.
 *
 * <p>Usage: {@code java ValidateDictionaries.java [--plan] [--xsd-dir DIR] [--only NAMES]
 * [--commands] DICTIONARY_DIR}.
 *
 * <p>Without {@code --only}, every {@code .xml} file of DICTIONARY_DIR is a candidate. {@code
 * --only A,B} limits the candidates to {@code A.xml} and {@code B.xml}; a name that has no file
 * stops the program with status 2. A command dictionary (root element {@code
 * diameter-command-dictionary}) is validated only with {@code --commands}; otherwise the program
 * prints how many it skipped. With {@code --commands} the output lists the dictionaries and the
 * command dictionaries in separate groups.
 *
 * <p>The schema of each file that is validated is chosen in this order:
 *
 * <ol>
 *   <li>the file's own {@code xsi:noNamespaceSchemaLocation} or {@code xsi:schemaLocation},
 *       resolved against the folder of the file;
 *   <li>if that file does not exist and {@code --xsd-dir} is given, the file of that name in
 *       DIR, when it declares the root element of the dictionary;
 *   <li>if the file has no reference, or none of the above applies, and {@code --xsd-dir} is
 *       given, the one {@code .xsd} file of DIR that declares the root element of the dictionary
 *       as a global element.
 * </ol>
 *
 * <p>Nothing is searched outside DIR. If any file has no schema, the program validates nothing,
 * lists the problems, and exits with status 3. With {@code --plan} it only prints the schema
 * chosen for each file. Errors of a file are grouped by message, with the line of the first
 * occurrence.
 *
 * <p>Exit status: 0 all valid, 1 some file invalid, 2 wrong arguments, 3 schemas not found.
 */
public class ValidateDictionaries {

  private static final int MAX_MESSAGE_LENGTH = 230;
  private static final int EXIT_UNRESOLVED = 3;
  private static final String XSI = "http://www.w3.org/2001/XMLSchema-instance";
  private static final String XS = "http://www.w3.org/2001/XMLSchema";
  private static final String COMMAND_ROOT = "diameter-command-dictionary";
  private static final String DICTIONARY_GROUP = "AVP dictionaries:";
  private static final String COMMAND_GROUP = "Command dictionaries (not used by the conversion):";

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

  /** A dictionary file, and the schema chosen for it or the reason there is none. */
  private static final class Entry {
    private final File file;
    private final String root;
    private final String reference;
    private File schema;
    private String how;
    private String problem;

    private Entry(File file, String root, String reference) {
      this.file = file;
      this.root = root;
      this.reference = reference;
    }

    private boolean isCommandDictionary() {
      return COMMAND_ROOT.equals(root);
    }

    private String group() {
      return isCommandDictionary() ? COMMAND_GROUP : DICTIONARY_GROUP;
    }
  }

  private static Document parse(File file) throws Exception {
    DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
    factory.setNamespaceAware(true);
    factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
    return factory.newDocumentBuilder().parse(file);
  }

  /** Returns the schema location that the root element names, or an empty string. */
  private static String referenceOf(Element root) {
    String single = root.getAttributeNS(XSI, "noNamespaceSchemaLocation").trim();
    if (!single.isEmpty()) {
      return single;
    }
    String[] pairs = root.getAttributeNS(XSI, "schemaLocation").trim().split("\\s+");
    return pairs.length >= 2 ? pairs[1] : "";
  }

  /** Maps each global element name to the .xsd files of the folder that declare it. */
  private static Map<String, List<File>> declaredRoots(File xsdDir) throws Exception {
    Map<String, List<File>> index = new TreeMap<>();
    File[] schemas = xsdDir.listFiles((d, name) -> name.endsWith(".xsd"));
    if (schemas == null) {
      return index;
    }
    Arrays.sort(schemas);
    for (File schema : schemas) {
      Element root = parse(schema).getDocumentElement();
      for (Node child = root.getFirstChild(); child != null; child = child.getNextSibling()) {
        if (child instanceof Element
            && XS.equals(child.getNamespaceURI())
            && "element".equals(child.getLocalName())) {
          String name = ((Element) child).getAttribute("name");
          index.computeIfAbsent(name, k -> new ArrayList<>()).add(schema);
        }
      }
    }
    return index;
  }

  private static void chooseByRoot(Entry entry, File xsdDir, Map<String, List<File>> index) {
    List<File> found = index.getOrDefault(entry.root, new ArrayList<>());
    if (found.size() == 1) {
      entry.schema = found.get(0);
      entry.how = "the only schema in " + xsdDir + " that declares <" + entry.root + ">";
    } else if (found.isEmpty()) {
      entry.problem = "no schema in " + xsdDir + " declares the root element <" + entry.root + ">";
    } else {
      entry.problem =
          "several schemas in " + xsdDir + " declare <" + entry.root + ">: " + names(found);
    }
  }

  private static String names(List<File> files) {
    List<String> names = new ArrayList<>();
    for (File file : files) {
      names.add(file.getName());
    }
    return String.join(", ", names);
  }

  /** Chooses the schema of one file, following the order in the class comment. */
  private static void resolve(Entry entry, File xsdDir, Map<String, List<File>> index) {
    String reference = entry.reference;
    if (reference.isEmpty()) {
      entry.problem = "the file has no schema reference";
    } else if (reference.contains("://")) {
      entry.problem =
          "the reference " + reference + " is a URL, and this program downloads nothing";
    } else {
      File named = new File(reference);
      File target = named.isAbsolute() ? named : new File(entry.file.getParentFile(), reference);
      if (target.isFile()) {
        entry.schema = target;
        entry.how = "the reference in the file";
        return;
      }
      entry.problem = "the reference " + reference + " does not resolve; no file " + target;
      if (xsdDir != null) {
        File sameName = new File(xsdDir, named.getName());
        if (index.getOrDefault(entry.root, new ArrayList<>()).contains(sameName)) {
          entry.schema = sameName;
          entry.how = "the name in the reference, in " + xsdDir;
          entry.problem = null;
          return;
        }
      }
    }
    if (xsdDir != null) {
      entry.problem = null;
      chooseByRoot(entry, xsdDir, index);
    }
  }

  private static List<Entry> plan(File[] files, File xsdDir) throws Exception {
    Map<String, List<File>> index = xsdDir == null ? new TreeMap<>() : declaredRoots(xsdDir);
    List<Entry> entries = new ArrayList<>();
    for (File file : files) {
      Element root = parse(file).getDocumentElement();
      Entry entry = new Entry(file, root.getLocalName(), referenceOf(root));
      resolve(entry, xsdDir, index);
      entries.add(entry);
    }
    return entries;
  }

  /** Prints the plan; returns the number of files that have no schema. */
  private static int printPlan(List<Entry> entries, boolean verbose, boolean groups) {
    Map<String, Integer> problems = new LinkedHashMap<>();
    String group = "";
    for (Entry entry : entries) {
      if (entry.problem != null) {
        group = heading(group, entry, groups);
        System.out.printf(
            "NO SCHEMA %s (%s): %s%n", entry.file.getName(), entry.root, entry.problem);
        problems.merge(entry.problem, 1, Integer::sum);
      } else if (verbose) {
        group = heading(group, entry, groups);
        System.out.printf(
            "%s (%s): %s, chosen by %s%n",
            entry.file.getName(), entry.root, entry.schema, entry.how);
      }
    }
    int files = problems.values().stream().mapToInt(Integer::intValue).sum();
    if (files > 0) {
      System.out.printf("%d distinct problem(s) in %d file(s):%n", problems.size(), files);
      for (Map.Entry<String, Integer> problem : problems.entrySet()) {
        System.out.printf("    %s (%d file(s))%n", problem.getKey(), problem.getValue());
      }
      System.out.printf(
          "Nothing is validated: %d of %d file(s) have no schema.%n", files, entries.size());
    }
    return files;
  }

  /** Prints the heading of the entry's group when the group changes; returns the current group. */
  private static String heading(String current, Entry entry, boolean groups) {
    if (!groups || entry.group().equals(current)) {
      return current;
    }
    System.out.println(entry.group());
    return entry.group();
  }

  /** Validates one file, prints the result, and returns the number of errors. */
  private static int validate(Entry entry, Map<File, Schema> schemas, SchemaFactory factory)
      throws Exception {
    Schema schema = schemas.get(entry.schema);
    if (schema == null) {
      schema = factory.newSchema(entry.schema);
      schemas.put(entry.schema, schema);
    }
    Collector collector = new Collector();
    Validator validator = schema.newValidator();
    validator.setErrorHandler(collector);
    try {
      validator.validate(new StreamSource(entry.file));
    } catch (SAXParseException e) {
      collector.messages.put("FATAL " + e.getMessage(), new int[] {1, e.getLineNumber()});
    }

    int total = collector.messages.values().stream().mapToInt(v -> v[0]).sum();
    String verdict = total == 0 ? "valid" : total + " errors";
    System.out.printf("%s (%s): %s%n", entry.file.getName(), entry.root, verdict);
    System.out.printf("    schema: %s%n", entry.schema);
    for (Map.Entry<String, int[]> error : collector.messages.entrySet()) {
      String message = error.getKey();
      if (message.length() > MAX_MESSAGE_LENGTH) {
        message = message.substring(0, MAX_MESSAGE_LENGTH) + "...";
      }
      int[] where = error.getValue();
      System.out.printf("    x%d, first at line %d: %s%n", where[0], where[1], message);
    }
    return total;
  }

  private static void usage() {
    System.err.println(
        "Usage: java ValidateDictionaries.java [--plan] [--xsd-dir DIR] [--only NAMES]"
            + " [--commands] DICTIONARY_DIR");
    System.exit(2);
  }

  private static void fail(String message) {
    System.err.println(message);
    System.exit(2);
  }

  /** Returns the candidate files: those named by {@code only}, or every .xml file of the folder. */
  private static File[] candidates(File dir, String only) {
    if (only == null) {
      File[] files = dir.listFiles((d, name) -> name.endsWith(".xml"));
      if (files == null || files.length == 0) {
        fail("No .xml files in " + dir);
      }
      Arrays.sort(files);
      return files;
    }
    List<File> files = new ArrayList<>();
    for (String name : only.split(",")) {
      String trimmed = name.trim();
      File file = new File(dir, trimmed.endsWith(".xml") ? trimmed : trimmed + ".xml");
      if (!file.isFile()) {
        fail("--only: no file " + file);
      }
      files.add(file);
    }
    return files.toArray(new File[0]);
  }

  /** Drops the command dictionaries unless they are asked for; puts the AVP dictionaries first. */
  private static List<Entry> select(List<Entry> all, boolean commands) {
    List<Entry> selected = new ArrayList<>();
    for (boolean wantCommands : new boolean[] {false, true}) {
      for (Entry entry : all) {
        if (entry.isCommandDictionary() == wantCommands && (commands || !wantCommands)) {
          selected.add(entry);
        }
      }
    }
    long skipped = all.stream().filter(Entry::isCommandDictionary).count();
    if (!commands && skipped > 0) {
      System.out.printf(
          "Not validated: %d command dictionary file(s), which the conversion does not use."
              + " Pass --commands to validate them.%n",
          skipped);
    }
    return selected;
  }

  public static void main(String[] args) throws Exception {
    boolean planOnly = false;
    boolean commands = false;
    String only = null;
    File xsdDir = null;
    File dir = null;
    for (int i = 0; i < args.length; i++) {
      if ("--plan".equals(args[i])) {
        planOnly = true;
      } else if ("--commands".equals(args[i])) {
        commands = true;
      } else if ("--only".equals(args[i]) && i + 1 < args.length) {
        only = args[++i];
      } else if ("--xsd-dir".equals(args[i]) && i + 1 < args.length) {
        xsdDir = new File(args[++i]);
      } else if (dir == null && !args[i].startsWith("--")) {
        dir = new File(args[i]);
      } else {
        usage();
      }
    }
    if (dir == null) {
      usage();
    }
    if (xsdDir != null && !xsdDir.isDirectory()) {
      fail("--xsd-dir is not a folder: " + xsdDir);
    }

    List<Entry> entries = select(plan(candidates(dir, only), xsdDir), commands);
    if (entries.isEmpty()) {
      fail("No AVP dictionary to validate in " + dir);
    }
    if (printPlan(entries, planOnly, commands) > 0) {
      System.exit(EXIT_UNRESOLVED);
    }
    if (planOnly) {
      System.exit(0);
    }

    SchemaFactory factory = SchemaFactory.newInstance(XMLConstants.W3C_XML_SCHEMA_NS_URI);
    factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
    Map<File, Schema> schemas = new LinkedHashMap<>();
    int invalid = 0;
    String group = "";
    for (Entry entry : entries) {
      group = heading(group, entry, commands);
      if (validate(entry, schemas, factory) > 0) {
        invalid++;
      }
    }
    System.out.printf("%d of %d files are invalid%n", invalid, entries.size());
    System.exit(invalid == 0 ? 0 : 1);
  }
}
